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
class RabbitmqSetup():
    pass


class RabbitmqActor(Actor):


    def __init__(self, config):
        super().__init__(self)
        self.config = config
        self.rabbitmq_url = None
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        self.rabbitmq_queue = None

        self.identity_string = None

        self.time_to_wait_for_additional_messages_at_close = 5



    async def connect_to_rabbit(self):
        # connect to rabbitmq
        # create rabbitmq stuff
        self.rabbitmq_url = self.config.rabbitmq_url

        self.identity_string = utils.get_identity_string()
        logger.info("Our identity string is `%s`", self.identity_string)
        # use with_password to clear the password when printing
        logger.info("connecting to rabbitmq url: `%r`", self.rabbitmq_url.with_password(None))
        self.rabbitmq_connection = await aio_pika.connect_robust(str(self.rabbitmq_url))
        logger.info("rabbitmq client connected: `%s`", self.rabbitmq_connection)
        self.rabbitmq_channel = await self.rabbitmq_connection.channel()
        logger.info("rabbitmq channel created: `%s`", self.rabbitmq_channel)

        self.rabbitmq_queue = await self.rabbitmq_channel.get_queue(name=self.config.rabbitmq_queue_name, ensure=True)
        logger.info("rabbitmq queue created: `%s`", self.rabbitmq_queue)

    async def shutdown_rabbit(self):

        logger.info("telling queue `%s` to cancel the consumer `%s`", self.rabbitmq_queue, self.identity_string)
        await self.rabbitmq_queue.cancel(consumer_tag=self.identity_string)

        logger.info("closing channel `%s`", self.rabbitmq_channel)
        await self.rabbitmq_channel.close()

        logger.info("closing connection `%s`", self.rabbitmq_connection)
        await self.rabbitmq_connection.close()

        logger.info("waiting for `%s` seconds to wait for any outstanding messages to finish...",
            self.time_to_wait_for_additional_messages_at_close)
        await asyncio.sleep(self.time_to_wait_for_additional_messages_at_close)


    async def handle_message(self, message: Message):

        logger.info("rabbitmq message: `%s`", message)
        d = message.data
        if d.__class__ == RabbitmqSetup:
            await self.connect_to_rabbit()

        if d.__class__ == PleaseStop:

            logger.info("being asked to stop")

            await self.shutdown_rabbit()

            await message.sender.tell(DataMessage(data="ok", sender=self))

            logger.info("Stopping self")
            raise EndMainLoop()
