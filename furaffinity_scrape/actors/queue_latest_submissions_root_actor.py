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
from furaffinity_scrape.actors.rabbitmq_actor import RabbitmqActor, RabbitmqSetup
from furaffinity_scrape.actors.common_actor_messages import PleaseStop

logger = logging.getLogger(__name__)


@attr.define(frozen=True)
class QueueLatestSubmissionsRootActorSetup():
    pass

class QueueLatestSubmissionsRootActor(Actor):


    def __init__(self, config):

        super().__init__(self)
        self.config = config

        self.rabbit_actor = None
        self.sqla_actor = None


    # def __init__(self, config):

    #     super()

    #     self.config = config

    async def setup(self):

        logger.info("setting up")

        # create rabbit actor
        self.rabbit_actor = await self.register_child(RabbitmqActor(self.config))

        await self.rabbit_actor.tell(DataMessage(data=RabbitmqSetup(), sender=self))


    async def shutdown(self):

        logger.info("stopping rabbit actor...")
        result = await self.rabbit_actor.ask(DataMessage(data=PleaseStop(), sender=self))
        logger.info("rabbit actor stopped with result: `%s`", result.data)

    async def handle_message(self, message: Message):


        # match statements are weird man
        # https://stackoverflow.com/questions/67525257/capture-makes-remaining-patterns-unreachable/67525259#67525259

        d = message.data
        if d.__class__ == QueueLatestSubmissionsRootActorSetup:
            await self.setup()

        elif d.__class__ == PleaseStop:
            logger.info("Asked to exit")

            await self.shutdown()

            logger.info("stopping self")

            await message.sender.tell(DataMessage(data="ok", sender=self))
            raise EndMainLoop()



