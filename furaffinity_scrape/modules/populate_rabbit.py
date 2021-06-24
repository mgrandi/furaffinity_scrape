import logging
import json
import asyncio

import aiorabbit
import aiorabbit.client

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

        self.rabbitmq_client = None

    async def close_stuff(self):

        if self.rabbitmq_client and not self.rabbitmq_client.is_closed:
            logger.info("closing rabbitmq client")
            await self.rabbitmq_client.close()
            self.rabbitmq_client = None


    async def run(self, parsed_args, stop_event):

        self.config = parsed_args.config

        try:

            # create rabbitmq stuff
            logger.info("connecting to rabbitmq: `%s`", self.config.rabbitmq_url)

            self.rabbitmq_client = aiorabbit.client.Client(str(self.config.rabbitmq_url))

            await self.rabbitmq_client.connect()
            logger.info("rabbitmq client connected")

            # for enabling publisher confirmation of published messages.
            #await self.rabbitmq_client.confirm_select()


            # consumer_tag = await self.rabbitmq_client.basic_consume(self.config.rabbitmq_queue_name, callback=self.on_message)

            # logger.info('Started consuming on queue %s with consumer tag %s',
            #          self.config.rabbitmq_queue_name, consumer_tag)

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
                publish_result = await self.rabbitmq_client.publish(
                    exchange="", # the exchange by default is `amq.direct`, but we need this to be the empty string to route it to the queue in `routing_key`
                    routing_key=self.config.rabbitmq_queue_name,
                    message_body=message_body)


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

