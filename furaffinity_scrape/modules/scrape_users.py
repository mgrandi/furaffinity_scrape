from __future__ import annotations
import logging
import typing
import asyncio
import socket
import os
import json

import attr
import yarl
from bs4 import BeautifulSoup
import aiohttp
from furl import furl
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

class ScrapeUsers:


    @staticmethod
    def create_subparser_command(argparse_subparser):
        '''
        populate the argparse arguments for this module

        @param argparse_subparser - the object returned by ArgumentParser.add_subparsers()
        that we call add_parser() on to add arguments and such

        '''

        parser = argparse_subparser.add_parser("scrape_users")

        scrape_users_obj = ScrapeUsers()

        # set the function that is called when this command is used
        parser.set_defaults(func_to_run=scrape_users_obj.run)


    def __init__(self):

        fqdn = socket.getfqdn()
        pid = os.getpid()
        self.identity_string = f"FQDN[{fqdn}]-PID[{pid}]"
        self.stop_event = None
        self.config = None
        self.sqla_engine = None
        self.async_sessionmaker = None
        self.rabbitmq_url:yarl.URL = None
        self.rabbitmq_client = None
        self.rabbitmq_channel = None
        self.rabbitmq_queue = None

        self.html_queries_list = []

        self.create_html_queries()


    def create_html_queries(self):

        to_add_list = [

            model.HtmlQuery(description="artist's username",
                func=html_utils.get_artist_username_as_list),

            model.HtmlQuery(description="commenter username",
                func=html_utils.get_commenter_usernames_as_list ),

            model.HtmlQuery(description="submission description avatar username links",
                func=html_utils.get_submission_description_avatar_usernames_as_list ),

            model.HtmlQuery(description="submission description link username links",
                func=html_utils.get_submission_description_link_usernames_as_list ),

            model.HtmlQuery(description="submission description url tag username links",
                func=html_utils.get_submission_description_autolink_usernames_as_list )

        ]

        self.html_queries_list.extend(to_add_list)

    async def update_or_ignore_found_users(self, users_found_set:set, session:AsyncSession, date_added:arrow.arrow.Arrow):
        '''
        queries the database for all of the users found in the set

        if we are using postgres, we can update the database using a special insert statement that has
        'on conflict do nothing' (an "upsert")

        see https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#insert-on-conflict-upsert

        note: originally we did this in ORM mode and asked the database for the list of users that we do a diff and see which
        users were already in the DB, and then inserted the missing users. We still do that, but now we do a upsert
        which means that if two workers have a race condition trying to add the same user, it won't have one worker fail,
        the losing worker will just have the "on conflict do nothing" take place and everyone is happy, and no database
        locking!

        '''

        select_statement = select(db_model.User) \
            .filter(db_model.User.user_name.in_(users_found_set))

        logger.debug("selecting data for user diff update: `%s`", select_statement)
        select_result = await session.execute(select_statement)

        users_in_database_list = select_result.scalars().all()
        logger.debug("got `%s` users in database", len(users_in_database_list))

        users_in_database_set = set([iter_user.user_name for iter_user in users_in_database_list])

        # now do a set difference
        users_not_in_db_set = users_found_set.difference(users_in_database_set)

        logger.debug("users to add (`%s`): `%s`, \n\nusers already in database (`%s`): `%s`, \n\nusers to insert into db (`%s`): `%s`",
            len(users_found_set),
            users_found_set,
            len(users_in_database_set),
            users_in_database_set,
            len(users_not_in_db_set),
            users_not_in_db_set)

        logger.info("found `%s` new users to add to the database: `%s`",
            len(users_not_in_db_set), users_not_in_db_set)

        # only do this if we have > 0 users to add, otherwise we will get an integrity error trying to add a
        # user that has null values
        if len(users_not_in_db_set) > 0:

            core_insert_values_list = []
            for iter_user_name in users_not_in_db_set:
                core_insert_values_list.append({"date_added": date_added, "user_name": iter_user_name})

            upsert_statement = insert(db_model.User.__table__).values(core_insert_values_list)

            upsert_statement.on_conflict_do_nothing(constraint="PK-user-user_id")

            # NOTE: potentially very verbose, uncomment for debugging
            # logger.debug("upsert statement: `%s`", upsert_statement)
            #
            conn = await session.connection()

            logger.debug("executing upsert statement")
            await conn.execute(upsert_statement)
            logger.debug("upsert statement finished successfully")

        else:

            logger.debug("no users to add to the database, not upserting anything")

    def does_submission_exist(self, current_fa_submission:model.FASubmission) -> model.SubmissionStatus:
        '''
        returns whether the submission exists or not depending on the html
        '''

        def _is_submission_deleted(soup):
            '''
            only the submission is deleted
            '''
            result = current_fa_submission.soup.select("div.section-body")

            if result:
                result_element = result[0]

                if result_element.text.strip() == constants.SUBMISSION_DOESNT_EXIST_TEXT:
                    return True

            return False

        def _is_submission_gdpr_deleted(soup):
            '''
            a "GDPR" delete, presumably the entire account + all submissions are deleted
            '''
            result = current_fa_submission.soup.select("body#pageid-error-account-unavailable-deleted")

            if result:
                result_element = result[0]
                return True

            return False


        if _is_submission_deleted(current_fa_submission.soup):
            logger.debug("submission `%s` was deleted", current_fa_submission)
            return model.SubmissionStatus.DELETED


        if _is_submission_gdpr_deleted(current_fa_submission.soup):
            logger.debug("submission `%s`, was GDPR deleted", current_fa_submission)
            return model.SubmissionStatus.GDPR_DELETED


        logger.debug("assuming submission `%s`, does exist", current_fa_submission)
        return model.SubmissionStatus.EXISTS

    def scrape_html(self, fa_submission):


        users_found_set = set()

        for iter_query in self.html_queries_list:

            logger.debug("scrape_html: starting function for `%s`", iter_query.description)
            result_set = set(iter_query.func(fa_submission.soup))

            # ogger.debug("query `%s` returned `%s` new users", iter_query.description, len(result_set))
            logger.debug("scrape_html: query `%s` returned `%s` unique users: `%s`", iter_query.description, len(result_set), result_set)


            # `update` only works on a set
            users_found_set.update(result_set)

        logger.info("found `%s` users", len(users_found_set))

        return users_found_set

    def add_webpage_data_to_db(self, sqla_session, fa_submission, current_date):
        '''
        given a FA submission and the current date, add a new row to SubmisisonWebPage

        @param sqla_session - the sqlalchemy session
        @param fa_submission - the FASubmission object to insert to the database
        @param current_date - the current date as an arrow object

        '''

        compress_and_hash_result = utils.compress_and_hash_text_data(fa_submission.raw_html_bytes)

        submission_wp = db_model.SubmissionWebpage(
            date_visited=current_date,
            submission=fa_submission.submission_row,
            raw_compressed_webpage_data=compress_and_hash_result.compressed_data,
            encoding_status=model.EncodingStatusEnum.DECODED_OK if not fa_submission.did_have_decode_error else model.EncodingStatusEnum.UNICODE_DECODE_ERROR,
            original_data_sha512=compress_and_hash_result.original_data_sha512,
            compressed_data_sha512=compress_and_hash_result.compressed_data_sha512)

        sqla_session.add(submission_wp)

    async def download_one_fa_submission(self, fa_submission, aiohttp_session) -> model.FASubmission:
        '''
        takes a FASubmission and a aiohttp session and downloads the FA submisison and return a
        evolved FASubmission with the BeautifulSoup, raw html bytes and decoding status
        updates

        @param fa_submission - the FASubmission object we are going to download
        @param aiohttp_session - the aiohttp session to use to download the fa submission
        @return a evolved FaSubmission object
        '''

        url = furl(constants.FURAFFINITY_URL_SUBMISSION.format(fa_submission.submission_row.furaffinity_submission_id))

        aiohttp_response_result = await utils.fetch_url(aiohttp_session, url)

        logger.debug("length of html: `%s`", len(aiohttp_response_result.decoded_text))

        soup = BeautifulSoup(aiohttp_response_result.decoded_text, "lxml")

        evolved_fa_submission = attr.evolve(
            fa_submission,
            raw_html_bytes=aiohttp_response_result.binary_data,
            soup=soup,
            did_have_decode_error=aiohttp_response_result.encountered_decoding_error)

        return evolved_fa_submission


    async def claim_next_submission(self, submission_id, sqla_session, current_date):
        '''

        "claims" the next submission

        this checks to see if we have a row in the submission table already for this submission, and if we do
        we see if it is finished or not

        if it was finished, then we will return None, to let the caller know that this was already finished but not acked
        for some reason (crashed at the perfect time?), since we use rabbitmq for the queueing, it is possible that
        it was finished but then it never got a chance to ack the message so it got returned to the queue

        if it wasn't finished, then we will just use that submission row and update the date

        if we DIDN'T find an existing submission, we will create a new FASubmission object and add it to the session
        where it will be added immediately to the database

        '''

        async with sqla_session.begin():

            # first off, see if this submission already was claimed by another worker and then that worker
            # crashed or something, returning the message to the queue. if that did happen, then we can use the existing
            # submission object
            does_submission_exist_stmt = select(db_model.Submission).where(db_model.Submission.furaffinity_submission_id == submission_id)

            maybe_existing_fa_submission_execute_result = await sqla_session.execute(does_submission_exist_stmt)

            # TODO: figure out this, i say 'one or None', but i get back a sequence , so i still have to do '[0]' on it,
            # i guess its better to return a sequence always so that way you aren't accidentally trying to get a index of a non sequence
            # if it returns only one?
            maybe_existing_fa_submission_sequence = maybe_existing_fa_submission_execute_result.one_or_none()

            logger.debug("Checking to see if there is a `Submission` row in the database for fa submission id `%s`, result is: `%s`",
                submission_id, maybe_existing_fa_submission_sequence)

            if maybe_existing_fa_submission_sequence:

                maybe_existing_fa_submission = maybe_existing_fa_submission_sequence[0]

                # there was an existing row, see if it was done already
                if maybe_existing_fa_submission.processed_status == model.ProcessedStatus.FINISHED:

                    # submission was already finished, return None to let caller know to skip this one
                    logger.info("Skipping submission with the FA submission id `%s` because it was already started, and finished in the database: `%s`",
                        submission_id, maybe_existing_fa_submission)
                    return None

                else:

                    # there was an existing row, but it was not finished already. Set a new date, and return it
                    logger.info("Submission with the FA submission id of `%s` was started but not finished, reusing existing submission object: `%s`",
                        maybe_existing_fa_submission)

                    maybe_existing_fa_submission.date_visited = current_date

                    sqla_session.add(maybe_existing_fa_submission)

                    return maybe_existing_fa_submission

            else:

                # no existing row was found, this is the expected path, create a new submission row

                logger.info("Submission with the FA submission id `%s` doesn't already exist in the database, creating a new one", submission_id)

                # insert the submission into the database to mark that are processing this
                new_submission_row = db_model.Submission(
                    furaffinity_submission_id=submission_id,
                    date_visited=current_date,
                    submission_status=model.SubmissionStatus.UNKNOWN,
                    processed_status=model.ProcessedStatus.TODO,
                    claimed_by=self.identity_string)

                logger.debug("adding new submission object to db: `%s`", new_submission_row)

                sqla_session.add(new_submission_row)

                return new_submission_row

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
                current_fa_submission = await self.download_one_fa_submission(current_fa_submission, aiohttp_session)

                # see if the submission exists
                submission_status = self.does_submission_exist(current_fa_submission)

                current_submission_row.submission_status = submission_status

                # if the submission does exist, save it in the database and scrape it for users
                # if it doesn't exist, don't do anything
                if submission_status == model.SubmissionStatus.EXISTS:

                    logger.info("submission exists, scraping html")

                    users_found_set = self.scrape_html(current_fa_submission)

                    # add the users to the database that we don't already have
                    await self.update_or_ignore_found_users(users_found_set, sqla_session, current_date)

                    # add the submission page data
                    self.add_webpage_data_to_db(sqla_session, current_fa_submission, current_date)

                else:

                    logger.info("submission doesn't exist, not searching for users")

                # now mark the submission as processed
                current_submission_row.processed_status = model.ProcessedStatus.FINISHED
                sqla_session.add(current_submission_row)

                # one with this FA submission
                logger.info("finished with submission `%s`", current_fa_submission)
                logger.debug("committing")

            logger.debug("committing done")


    def return_rabbitmq_message_received_callback(self, aiohttp_session, sessionmaker):

        async def rabbitmq_message_received(msg: aio_pika.IncomingMessage) -> None:

            message_alternate_representation = model.RabbitmqMessageInfo(delivery_tag=msg.delivery_tag, body_bytes=msg.body )
            logger.debug("rabbitmq_message_received() called with message: `%s`", message_alternate_representation)

            try:

                submission_str = msg.body.decode("utf-8")
                logger.debug("submission id as string: `%s`", submission_str)
                submission_id = int(submission_str)

                if not isinstance(submission_id, int):
                    raise Exception(f"submission id wasn't an integer? rabbitmq message was: `{message_alternate_representation}`, submission id was `{submission_id}`" )

                await self.one_iteration(submission_id, aiohttp_session, self.async_sessionmaker)

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


    async def run(self, parsed_args, stop_event):

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

            # create databases if they don't exist already
            async with self.sqla_engine.begin() as conn:
                await conn.run_sync(db_model.CustomDeclarativeBase.metadata.create_all)

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

                logger.info("run() loop ended, stop_event was set! Returning")

            await self.close_stuff()


        except Exception as e:
            logger.exception("uncaught exception")
            await self.close_stuff()
            raise e



