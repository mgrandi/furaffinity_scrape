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


from furaffinity_scrape import utils
from furaffinity_scrape import db_model
from furaffinity_scrape import model
from furaffinity_scrape.actors.common_actor_messages import PleaseStop

logger = logging.getLogger(__name__)


@attr.define(frozen=True)
class SetupSqlaActor:
    pass

@attr.define(frozen=True)
class GetLatestFuraffinitySubmissionInDatabase:
    pass

@attr.define(frozen=True)
class GetLatestFuraffinitySubmissionInDatabaseResult:

    latest_submission:int

class SqlalchemyActor(Actor):

    def __init__(self, config:model.Settings):

        super().__init__(self)

        self.config = config
        self.sqla_engine = None
        self.async_sessionmaker = None

    async def connect_to_database(self):

        logger.debug("setting up sqlalchemy actor")

        self.sqla_engine = utils.setup_sqlalchemy_engine(self.config.sqla_url)

        # expire_on_commit=False will prevent attributes from being expired
        # after commit.
        self.async_sessionmaker = sessionmaker(
            bind=self.sqla_engine, expire_on_commit=False, class_=AsyncSession
        )

    async def get_latest_finished_fa_submission(self) -> GetLatestFuraffinitySubmissionInDatabaseResult:

        logger.debug("fetching latest FA submission")
        async with self.async_sessionmaker() as sqla_session:

            statement = select(db_model.FAScrapeAttempt.furaffinity_submission_id).\
                order_by(desc(db_model.FAScrapeAttempt.furaffinity_submission_id)).limit(1)

            logger.debug("executing sql statement: `%s`", statement)

            tmp_result = await sqla_session.execute(statement)

            top_fa_id = tmp_result.fetchone().furaffinity_submission_id
            logger.debug("top fa id is `%s`", top_fa_id)

            return top_fa_id



    async def shutdown(self):

        logger.info("Closing Sqlachemy Engine: `%s`", self.sqla_engine)
        await self.sqla_engine.dispose()


    async def handle_message(self, message: Message):

        d = message.data
        if d.__class__ == SetupSqlaActor:
            await self.connect_to_database()

        elif d.__class__ == GetLatestFuraffinitySubmissionInDatabase:

            top_id = await self.get_latest_finished_fa_submission()
            result_msg = GetLatestFuraffinitySubmissionInDatabaseResult(latest_submission=top_id)
            await message.sender.tell(DataMessage(data=result_msg, sender=self))

        elif  d.__class__ == PleaseStop:

            logger.info("being asked to stop")

            await self.shutdown()

            await message.sender.tell(DataMessage(data="ok", sender=self))

            logger.info("Stopping self")
            raise EndMainLoop()


