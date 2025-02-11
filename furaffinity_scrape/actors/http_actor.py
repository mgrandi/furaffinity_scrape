import asyncio
import logging

import aiohttp
import attr
from actorio import Actor, Message, DataMessage, ask, EndMainLoop
import yarl
from bs4 import BeautifulSoup

from apscheduler.triggers.cron import CronTrigger
from apscheduler.jobstores.memory import MemoryJobStore
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor

from furaffinity_scrape import utils
from furaffinity_scrape import db_model
from furaffinity_scrape import model
from furaffinity_scrape.actors.sqlalchemy_actor import GetLatestFuraffinitySubmissionInDatabase
from furaffinity_scrape.actors.common_actor_messages import PleaseStop

logger = logging.getLogger(__name__)


@attr.define(frozen=True)
class HttpActorSetup:
    pass

@attr.define
class DownloadUrlRequest:
    url_to_download:yarl.URL

@attr.define
class DownloadUrlResult:
    url_downloaded:yarl.URL
    was_successful:bool
    exception:Exception|None
    result_html:BeautifulSoup|None = attr.field(repr=False)


class HttpActor(Actor):

    def __init__(self ,
        config:model.Settings):

        super().__init__(self)

        self.config = config
        self.cookie_dict = self.config.cookie_jar.as_aiohttp_cookie_dict()
        self.header_dict = self.config.header_jar.as_aiohttp_header_dict()
        self.client_session:asyncio.ClientSession = aiohttp.ClientSession(
            cookies=self.cookie_dict,
            headers=self.header_dict)

    async def setup(self):

        pass

    async def shutdown(self):

        logger.info("Closing ClientSession: `%s`", self.client_session)
        await self.client_session.close()


    async def download_url(self, download_url_request:DownloadUrlRequest) -> DownloadUrlResult:

        logger.debug("Downloading url `%s`", download_url_request)
        result:model.AiohttpResponseResult = None

        try:

             result = await utils.fetch_url(self.client_session, download_url_request.url_to_download)


        except aiohttp.ClientError as e:
            logger.exception("caught exception while reading url `%s`", download_url_request)

            return DownloadUrlResult(
                url_downloaded=download_url_request.url_to_download,
                was_successful=False,
                exception=e,
                result_html=None)

        # we got the html data as bytes, parse as beautifulsoup which uses
        # its own library to get the unicode encoding
        # https://beautiful-soup-4.readthedocs.io/en/latest/#encodings
        soup = None

        try:
            soup = BeautifulSoup(result.binary_data, "lxml")


        except Exception as e:
            logger.exception("caught exception while parsing the downloaded html as a BeautifulSoup (maybe encoding problem too...) `%s`",
             download_url_request)

            return DownloadUrlResult(
                url_downloaded=download_url_request.url_to_download,
                was_successful=False,
                exception=e,
                result_html=None)


        # now can return result
        return DownloadUrlResult(
            url_downloaded=download_url_request.url_to_download,
            was_successful=True,
            exception=None,
            result_html=soup)

    async def handle_message(self, message: Message):


        # match statements are weird man
        # https://stackoverflow.com/questions/67525257/capture-makes-remaining-patterns-unreachable/67525259#67525259

        d = message.data
        if d.__class__ == HttpActorSetup:
            await self.setup()

        elif d.__class__ == DownloadUrlRequest:
            res = await self.download_url(d)

            await message.sender.tell(DataMessage(data=res, sender=self))


        elif d.__class__ == PleaseStop:
            logger.info("Asked to exit")
            await self.shutdown()
            await message.sender.tell(DataMessage(data="ok", sender=self))

