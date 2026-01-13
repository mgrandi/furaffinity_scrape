import asyncio
import logging
import re

import bs4
import aio_pika
import arrow
from sqlalchemy import select, desc, text, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
import attr
from actorio_ng import Actor, Message, DataMessage, ask, EndMainLoop
import dateutil.tz
import yarl

from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor

from furaffinity_scrape import utils
from furaffinity_scrape import db_model
from furaffinity_scrape import model
from furaffinity_scrape import constants
from furaffinity_scrape.actors.sqlalchemy_actor import GetLatestFuraffinitySubmissionInDatabase
from furaffinity_scrape.actors.common_actor_messages import PleaseStop
from furaffinity_scrape.actors.http_actor import DownloadUrlResult, DownloadUrlRequest
from furaffinity_scrape.actors.rabbitmq_publish_actor import PublishRangeOfMessages


logger = logging.getLogger(__name__)


@attr.define(frozen=True)
class SchedulerSetup:
    pass

class QueueLatestSubmissionsSchedulerActor(Actor):

    def __init__(self ,
        config:model.Settings,
        sqla_actor:Actor,
        http_actor:Actor,
        rabbit_actor:Actor):

        super().__init__(self)

        self.config = config

        # sqlalchemy actor
        self.sqla_actor:Actor = sqla_actor
        # http actor
        self.http_actor:Actor = http_actor

        self.rabbit_actor:Actor = rabbit_actor

        # apscheduler items
        self.cron_trigger = None
        self.scheduler = None
        self.job_store = None
        self.executor = None
        self.scheduled_job = None
        self.job_id = "scheduled_job"

        # loop for the apscheduler trigger call
        self.loop = None

        self.submission_href_regex = re.compile(constants.FURAFFINITY_SUBMISSION_HREF_ID_REGEX)


    async def setup(self):

        logger.debug("setting up scheduler actor")

        self.loop = asyncio.get_running_loop()

        # set up apscheduler items
        self.cron_trigger = CronTrigger.from_crontab(
            self.config.queue_latest_submissions_settings.cron_string,
            timezone=dateutil.tz.UTC)
        self.scheduler = AsyncIOScheduler()
        self.executor = AsyncIOExecutor()
        self.scheduler.add_executor(self.executor)
        self.job_store = MemoryJobStore()

        # start the apscheduler scheduler
        self.scheduler.start()

        # add the job after starting the scheduler
        # we need to schedule it using a task on the loop
        # variable we saved because APScheduler doesn't have asyncio
        # support for running coroutines natively
        self.scheduled_job =  self.scheduler.add_job(
            lambda: self.loop.create_task(self.scheduled_func()),
            trigger=self.cron_trigger,
            id=self.job_id)

        logger.info("added job: `%s` with trigger `%s` using scheduler `%s`",
            self.scheduled_job, self.cron_trigger, self.scheduler)

    def shutdown(self):

        self.job_store.remove_all_jobs()
        self.job_store.shutdown()
        self.scheduler.shutdown()
        self.executor.shutdown()

        # the actors we have a reference to will be shut down elsewhere


    def get_latest_submission_id_from_soup(self, soup:bs4.BeautifulSoup) -> int|None:
        '''
        we have submisisons, get the latest one. So the latest submisisons are actually
        sorted by Art, Writing, Music, and Crafts, but it is easier to search for the latest
        art entry and even if we miss the 'actual' latest one (because it is Music/writing/crafts),
        we will pick it up next run
        '''

        submissions_a_tag_list = soup.select("#gallery-frontpage-submissions figure a[href]")

        if len(submissions_a_tag_list) == 0:
            logger.error("could not find any submissions in the beautiful soup object")
            return None


        latest_submission_a_tag = submissions_a_tag_list[0]
        latest_submission_href = latest_submission_a_tag["href"]
        logger.debug("latest submission href: `%s`", latest_submission_href)

        latest_submission_id_match:re.Match|None = self.submission_href_regex.search(latest_submission_href)
        if not latest_submission_id_match:
            logger.error("got None back after using regex `%s` to search for the id in `%s`",
                self.submission_href_regex, latest_submission_href)
            return None

        latest_submission_groupdict:dict = latest_submission_id_match.groupdict()
        if constants.FURAFFINITY_SUBMISSION_HREF_ID_REGEX_GROUP not in latest_submission_groupdict.keys():
            logger.error("got back a match `%s` but the expected group of `%s` was not inside? groupdict keys were `%s`",
                latest_submission_id_match,
                constants.FURAFFINITY_SUBMISSION_HREF_ID_REGEX_GROUP,
                latest_submission_groupdict.keys())
            return None

        # finally get the id oh my word
        latest_submission_id = latest_submission_groupdict[constants.FURAFFINITY_SUBMISSION_HREF_ID_REGEX_GROUP]

        logger.info("latest submission ID is: `%s`", latest_submission_id)

        return int(latest_submission_id)

    async def scheduled_func(self):

        logger.debug("scheduled function triggered to fetch latest furaffinity submission")

        # send message to the sqlalchemy actor
        latest_in_db_result_msg:DataMessage = await self.sqla_actor.ask(
            DataMessage(
                data=GetLatestFuraffinitySubmissionInDatabase(),
                sender=self) )
        latest_result_in_db:GetLatestFuraffinitySubmissionInDatabaseResult = latest_in_db_result_msg.data

        logger.debug("highest furaffinity submission is: `%s`", latest_result_in_db)

        # query the furaffinity homepage for the highest submission
        download_result:DataMessage = await self.http_actor.ask(
            DataMessage(
                data=DownloadUrlRequest(yarl.URL("https://furaffinity.net")),
                sender=self))

        logger.debug("downloaded homepage result is `%s`", download_result.data)


        # get the latest submisison
        soup:bs4.BeautifulSoup = download_result.data.result_html

        latest_id:int = self.get_latest_submission_id_from_soup(soup)

        # send the rabbitmq publish actor to publish the range of messages
        publish_obj = PublishRangeOfMessages(
            start_submission_number=latest_result_in_db.latest_submission+1,
            end_submission_number=latest_id)

        logger.info("telling rabbitmq actor to publish the range of messages: `%s`", publish_obj)
        publish_result:DataMessage = await self.rabbit_actor.ask(DataMessage(data=publish_obj, sender=self))
        logger.info("rabbitmq actor result of publishing range of messages was `%s`", publish_result.data)


    async def handle_message(self, message: Message):

        d = message.data
        if d.__class__ == SchedulerSetup:
            await self.setup()


        elif d.__class__ == PleaseStop:

            logger.info("being asked to stop")

            self.shutdown()

            await message.sender.tell(DataMessage(data="ok", sender=self))

            logger.info("Stopping self")
            raise EndMainLoop()

