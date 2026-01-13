import asyncio
import logging

from aiormq.exceptions import AMQPError
import aio_pika
from aio_pika.abc import DeliveryMode
import arrow
from sqlalchemy import select, desc, text, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
import attr
from actorio_ng import Actor, Message, DataMessage, ask, EndMainLoop


from furaffinity_scrape import utils
from furaffinity_scrape import db_model
from furaffinity_scrape import model
from furaffinity_scrape.actors.common_actor_messages import PleaseStop

logger = logging.getLogger(__name__)


@attr.define(frozen=True)
class RabbitmqSetup:
    pass


@attr.define(frozen=True)
class PublishRangeOfMessages:
    start_submission_number:int
    end_submission_number:int

@attr.define(frozen=True)
class PublishRangeOfMessagesResult:
    maybe_exception:Exception|None
    was_successful:bool
    publish_obj:PublishRangeOfMessages


class RabbitmqPublishActor(Actor):


    def __init__(self, config):
        super().__init__(self)
        self.config = config
        self.rabbitmq_url = None
        self.rabbitmq_connection = None
        self.rabbitmq_channel = None
        #self.rabbitmq_queue = None

        self.identity_string = None

        self.time_to_wait_for_additional_messages_at_close = 5

        self.prefetch_count:int = 1


    async def handle_publish_range_of_messages(self, publish_range_obj:PublishRangeOfMessages) -> PublishRangeOfMessagesResult:

        logger.info("publishing messages: `%s` to the queue `%s`",
            publish_range_obj,
            self.config.rabbitmq_queue_name)

        try:
            # publish the messages
            for idx in range(
                publish_range_obj.start_submission_number,
                publish_range_obj.end_submission_number + 1 ):

                # from https://www.rabbitmq.com/tutorials/tutorial-three-python.html
                # The exchange parameter is the name of the exchange. The empty
                # string denotes the default or nameless exchange: messages are
                # routed to the queue with the name specified by routing_key, if it exists.

                message_body = f"{idx}"

                message_to_publish = aio_pika.Message(
                    body=message_body.encode("utf-8"),
                    delivery_mode=DeliveryMode.PERSISTENT )

                publish_result = await self.rabbitmq_channel.default_exchange.publish(
                    message=message_to_publish,
                    routing_key=self.config.rabbitmq_queue_name)
        except AMQPError as e:
            logger.exception("exception caught publishing rabbitmq messages for publish range object `%s`",
                publish_range_obj)

            return PublishRangeOfMessagesResult(
                maybe_exception=e,
                was_successful=False,
                publish_obj=publish_range_obj)

        return PublishRangeOfMessagesResult(
            maybe_exception=None,
            was_successful=True,
            publish_obj=publish_range_obj)

    async def connect_to_rabbit(self):

        logger.debug("setting up rabbitmq actor")

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

        # Maximum message count which will be
        # processing at the same time.
        await self.rabbitmq_channel.set_qos(prefetch_count=self.prefetch_count)
        logger.info("setting rabbitmq prefetch count to be `%s`", self.prefetch_count)

        # self.rabbitmq_queue = await self.rabbitmq_channel.get_queue(name=self.config.rabbitmq_queue_name, ensure=True)
        # logger.info("rabbitmq queue created: `%s`", self.rabbitmq_queue)

    async def shutdown_rabbit(self):

        # logger.info("telling queue `%s` to cancel the consumer `%s`", self.rabbitmq_queue, self.identity_string)
        # await self.rabbitmq_queue.cancel(consumer_tag=self.identity_string)

        logger.info("closing channel `%s`", self.rabbitmq_channel)
        await self.rabbitmq_channel.close()

        logger.info("closing connection `%s`", self.rabbitmq_connection)
        await self.rabbitmq_connection.close()

        logger.info("waiting for `%s` seconds to wait for any outstanding messages to finish...",
            self.time_to_wait_for_additional_messages_at_close)
        await asyncio.sleep(self.time_to_wait_for_additional_messages_at_close)


    async def handle_message(self, message: Message):

        d = message.data
        if d.__class__ == RabbitmqSetup:
            await self.connect_to_rabbit()

        elif d.__class__ == PublishRangeOfMessages:
            result = await self.handle_publish_range_of_messages(d)
            await message.sender.tell(DataMessage(data=result, sender=self))

        elif d.__class__ == PleaseStop:

            logger.info("being asked to stop")

            await self.shutdown_rabbit()

            await message.sender.tell(DataMessage(data="ok", sender=self))

            logger.info("Stopping self")
            raise EndMainLoop()
