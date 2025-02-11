import asyncio
import logging

import aio_pika
import arrow
from sqlalchemy import select, desc, text, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
import attr
from actorio import Actor, Message, DataMessage, ask, EndMainLoop
import dateutil.tz
import yarl

from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor

from furaffinity_scrape import utils
from furaffinity_scrape import db_model
from furaffinity_scrape import model
from furaffinity_scrape.actors.sqlalchemy_actor import GetLatestFuraffinitySubmissionInDatabase
from furaffinity_scrape.actors.common_actor_messages import PleaseStop
from furaffinity_scrape.actors.http_actor import DownloadUrlResult, DownloadUrlRequest


logger = logging.getLogger(__name__)


@attr.define(frozen=True)
class SchedulerSetup:
    pass

class QueueLatestSubmissionsSchedulerActor(Actor):

    def __init__(self ,
        config:model.Settings,
        sqla_actor:Actor,
        http_actor:Actor):

        super().__init__(self)

        self.config = config

        # sqlalchemy actor
        self.sqla_actor:Actor = sqla_actor
        # http actor
        self.http_actor:Actor = http_actor

        # apscheduler items
        self.cron_trigger = None
        self.scheduler = None
        self.job_store = None
        self.executor = None
        self.scheduled_job = None
        self.job_id = "scheduled_job"

        # loop for the apscheduler trigger call
        self.loop = None


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



    async def scheduled_func(self):

        logger.debug("scheduled function triggered to fetch latest furaffinity submission")

        # send message to the sqlalchemy actor
        highest_id:DataMessage = await self.sqla_actor.ask(
            DataMessage(
                data=GetLatestFuraffinitySubmissionInDatabase(),
                sender=self) )

        logger.debug("highest furaffinity submission is: `%s`", highest_id.data)

        # query the furaffinity homepage for the highest submission
        download_result:DataMessage = await self.http_actor.ask(
            DataMessage(
                data=DownloadUrlRequest(yarl.URL("https://furaffinity.net")),
                sender=self))

        logger.debug("downloaded homepage result is `%s`", download_result.data)


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

