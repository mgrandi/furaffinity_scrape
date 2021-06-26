import logging
import json
import asyncio

import aio_pika

logger = logging.getLogger(__name__)

class PopulateRabbit:


    @staticmethod
    def create_subparser_command(argparse_subparser):
        '''
        populate the argparse arguments for this module

        @param argparse_subparser - the object returned by ArgumentParser.add_subparsers()
        that we call add_parser() on to add arguments and such

        '''

        parser = argparse_subparser.add_parser("populate_rabbit")

        populate_rabbit_obj = PopulateRabbit()

        # set the function that is called when this command is used
        parser.set_defaults(func_to_run=populate_rabbit_obj.run)


    def __init__(self):

        self.config = None

        self.rabbitmq_connection = None
        self.rabbitmq_url = None
        self.rabbitmq_channel = None
        self.rabbitmq_queue = None


    async def close_stuff(self):

        if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
            logger.info("closing rabbitmq client")
            await self.rabbitmq_connection.close()
            self.rabbitmq_connection = None


    async def run(self, parsed_args, stop_event):

        self.config = parsed_args.config

        try:

            # create rabbitmq stuff
            self.rabbitmq_url = self.config.rabbitmq_url

            # use with_password to clear the password when printing
            logger.info("connecting to rabbitmq url: `%r`", self.rabbitmq_url.with_password(None))
            self.rabbitmq_connection = await aio_pika.connect_robust(str(self.rabbitmq_url))
            logger.info("rabbitmq client connected")

            self.rabbitmq_channel = await self.rabbitmq_connection.channel(publisher_confirms=False)


            logger.info("populating rabbitmq with submission ids `%s` to `%s`", self.config.starting_submission_id, self.config.ending_submission_id)

            for iter_fa_submission_id in range(self.config.starting_submission_id, self.config.ending_submission_id + 1):

                if stop_event.is_set():
                    logger.info("stop event is set, breaking")
                    break

                # from https://www.rabbitmq.com/tutorials/tutorial-three-python.html
                # The exchange parameter is the name of the exchange. The empty
                # string denotes the default or nameless exchange: messages are
                # routed to the queue with the name specified by routing_key, if it exists.

                message_body = f"{iter_fa_submission_id}"

                # see https://aiorabbit.readthedocs.io/en/latest/api.html#aiorabbit.client.Client.publish

                message_to_publish = aio_pika.Message(body=message_body.encode("utf-8"))
                publish_result = await self.rabbitmq_channel.default_exchange.publish(
                    message=message_to_publish,
                    routing_key=self.config.rabbitmq_queue_name)


                # if not publish_result:
                #     raise Exception(f"error publishing message for submission id `{iter_fa_submission_id}`")

                if iter_fa_submission_id % 10000 == 0:

                    logger.info("%s/%s done", iter_fa_submission_id, self.config.ending_submission_id)
                    await asyncio.sleep(10)


                # logger.info("sleeping `%s`", iter_fa_submission_id)
                # await asyncio.sleep(10)

            logger.info("%s/%s done", self.config.ending_submission_id, self.config.ending_submission_id)

            # await stop_event.wait()

            await self.close_stuff()





        except Exception as e:
            logger.exception("uncaught exception")
            await self.close_stuff()
            raise e

