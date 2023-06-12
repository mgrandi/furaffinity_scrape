from __future__ import annotations
import logging
import typing
import asyncio
import json

import attr
import yarl
from bs4 import BeautifulSoup
import aiohttp
import arrow
from sqlalchemy import select, desc, text
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

import aio_pika

from furaffinity_scrape import utils
from furaffinity_scrape import db_model
from furaffinity_scrape import model
from furaffinity_scrape import constants
from furaffinity_scrape import html_utils

logger = logging.getLogger(__name__)

class ScrapeSubmissions:


    @staticmethod
    def create_subparser_command(argparse_subparser):
        '''
        populate the argparse arguments for this module

        @param argparse_subparser - the object returned by ArgumentParser.add_subparsers()
        that we call add_parser() on to add arguments and such

        '''

        parser = argparse_subparser.add_parser("scrape_submissions")

        scrape_submissions_obj = ScrapeSubmissions()

        # set the function that is called when this command is used
        parser.set_defaults(func_to_run=scrape_submissions_obj.run)


    def __init__(self):

        self.config = None

        self.rabbitmq_connection = None
        self.rabbitmq_url = None
        self.rabbitmq_channel = None
        self.rabbitmq_queue = None
        self.identity_string = None

        self.time_to_wait_for_additional_messages_at_close = 5

    async def run(self, parsed_args, stop_event):


        self.identity_string = utils.get_identity_string()
        logger.info("Our identity string is `%s`", self.identity_string)

        self.config = parsed_args.config
        self.sqla_engine = utils.setup_sqlalchemy_engine(self.config.sqla_url)
        self.stop_event = stop_event

        # create rabbitmq stuff
        self.rabbitmq_url = self.config.rabbitmq_url

        # use with_password to clear the password when printing
        logger.info("connecting to rabbitmq url: `%r`", self.rabbitmq_url.with_password(None))
        self.rabbitmq_connection = await aio_pika.connect_robust(str(self.rabbitmq_url))
        logger.info("rabbitmq client connected")

        self.rabbitmq_channel = await self.rabbitmq_connection.channel()

        # Maximum message count which will be
        # processing at the same time.
        await self.rabbitmq_channel.set_qos(prefetch_count=1)

        self.rabbitmq_queue = await self.rabbitmq_channel.get_queue(name=self.config.rabbitmq_queue_name, ensure=True)


        try:

            # expire_on_commit=False will prevent attributes from being expired
            # after commit.
            self.async_sessionmaker = sessionmaker(
                bind=self.sqla_engine, expire_on_commit=False, class_=AsyncSession
            )

            cookie_dict = self.config.cookie_jar.as_aiohttp_cookie_dict()
            header_dict = self.config.header_jar.as_aiohttp_header_dict()

            async with aiohttp.ClientSession(cookies=cookie_dict, headers=header_dict) as aiohttp_session:

                # uncomment this out when we configure our own httpbin instance to not
                # leak cookies to a public instance that we don't control
                # await utils.log_aiohttp_sessions_and_cookies(aiohttp_session)
                logger.info("starting rabbitmq basic_consume using consumer tag `%s`", self.identity_string)

                await self.rabbitmq_queue.consume(
                    callback=self.return_rabbitmq_message_received_callback(aiohttp_session, self.async_sessionmaker),
                    consumer_tag=self.identity_string)

                logger.info("waiting for stop event...")

                await self.stop_event.wait()

                logger.info("telling queue `%s` to cancel the consumer `%s`", self.rabbitmq_queue, self.identity_string)
                await self.rabbitmq_queue.cancel(consumer_tag=self.identity_string)

                logger.info("waiting for `%s` seconds to wait for any outstanding messages to finish...",
                    self.time_to_wait_for_additional_messages_at_close)
                await asyncio.sleep(self.time_to_wait_for_additional_messages_at_close)

                logger.info("run() loop ended, stop_event was set! Returning")

            await self.close_stuff()


        except Exception as e:
            logger.exception("uncaught exception")
            await self.close_stuff()
            raise e



    def return_rabbitmq_message_received_callback(self, aiohttp_session, sessionmaker):

        async def rabbitmq_message_received(msg: aio_pika.IncomingMessage) -> None:

            message_alternate_representation = model.RabbitmqMessageInfo(delivery_tag=msg.delivery_tag, body_bytes=msg.body )
            logger.debug("rabbitmq_message_received() called with message: `%s`", message_alternate_representation)

            if self.stop_event.is_set():
                # stop event is set, immediately nack the message
                logger.info("nacking message `%s` because stop event is set", message_alternate_representation)
                await msg.reject(requeue=True)
                return

            try:

                submission_str = msg.body.decode("utf-8")
                logger.debug("submission id as string: `%s`", submission_str)
                submission_id = int(submission_str)

                if not isinstance(submission_id, int):
                    raise Exception(f"submission id wasn't an integer? rabbitmq message was: `{message_alternate_representation}`, submission id was `{submission_id}`" )


                #await self.one_iteration(submission_id, aiohttp_session, self.async_sessionmaker)

                logger.debug("sleeping for `%s` second(s)", self.config.time_between_requests_seconds)
                await asyncio.sleep(self.config.time_between_requests_seconds)

                logger.info("acking message `%s`", message_alternate_representation)
                await msg.ack(multiple=False)

            except Exception as e:
                # don't rethrow as i don't think it will bubble up to the right place anyway, set the stop event instead
                logger.exception("Exception `%s` caught in rabbitmq_message_received processing message `%s`, nacking message, setting stop event", e, message_alternate_representation)

                # nack the message
                await msg.reject(requeue=True)

                self.stop_event.set()

        return rabbitmq_message_received


    async def one_iteration(self, submission_id, aiohttp_session, sessionmaker):

        current_date = arrow.utcnow()

        current_submission_row = None

        # TODO lock here
        async with sessionmaker() as sqla_session:

            # claim the latest submission and commit it
            # EDIT: now we are getting it from rabbitmq, but continue to use this to insert a submission record in the
            # database in case it randomly dies or something and rabbitmq also loses the message
            current_submission_row = await self.claim_next_submission(submission_id, sqla_session, current_date)

            if not current_submission_row:

                # if it was None, that means we have picked up a rabbit message for a submission that was started
                # and already finished, just return here so we skip the submission

                return

        async with sessionmaker() as sqla_session:


            async with sqla_session.begin():

                current_fa_submission = model.FASubmission(
                    submission_row=current_submission_row,
                    raw_html_bytes=None,
                    soup=None,
                    did_have_decode_error=None)

                logger.info("on submission `%s`", current_fa_submission)

                # now get the webpage
                pass

    async def close_stuff(self):

        # make sure we dispose the engine because its not in an `async with` block

        if self.sqla_engine:
            logger.info("closing sqla engine")
            await self.sqla_engine.dispose()
            self.sqla_engine = None

        if self.rabbitmq_connection and not self.rabbitmq_connection.is_closed:
            logger.info("closing rabbitmq client")
            await self.rabbitmq_connection.close()
            self.rabbitmq_connection = None