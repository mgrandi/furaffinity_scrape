from __future__ import annotations
import logging
import typing
import asyncio

import attr
from bs4 import BeautifulSoup
import aiohttp
from furl import furl
import arrow
from sqlalchemy import select, desc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from furaffinity_scrape import utils
from furaffinity_scrape import db_model
from furaffinity_scrape import model
from furaffinity_scrape import constants

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

        self.stop_event = None
        self.config = None
        self.sqla_engine = None
        self.async_sessionmaker = None
        self.current_submission_counter = -1

        self.html_queries_list = []

        self.create_html_queries()


    def create_html_queries(self):


        def _get_artist_username(soup):
            result_list = utils.make_soup_query_and_validate_number(
                soup=soup,
                query="div.submission-id-avatar > a",
                number_of_elements_expected=1)

            # href="/user/dragoneer/"
            artist_avatar_link = result_list[0]["href"]

            artist_username = artist_avatar_link.split("/")[2].lower()

            return [artist_username]

        def _get_commenter_usernames(soup):


            result_list = utils.make_soup_query_and_validate_number(
                soup=soup,
                query="strong.comment_username > h3",
                number_of_elements_expected=-1)

            return [iter_element.text.strip().lower() for iter_element in result_list]

        to_add_list = [

            model.HtmlQuery(description="artist's username",
                func=_get_artist_username),

            model.HtmlQuery(description="commenter username",
                func=_get_commenter_usernames )


        ]

        self.html_queries_list.extend(to_add_list)

    async def get_latest_item_from_submission_counter(self, session:AsyncSession) -> typing.Optional[db_model.SubmissionCounter]:

        logger.debug("fetching one row from SubmissionCounter ")
        stmt = select(db_model.SubmissionCounter).order_by(desc("submission_id")).limit(1)

        res = await session.execute(stmt)

        logger.debug("SubmissionCounter result: `%s`", res)

        return res.one_or_none()

    async def update_or_ignore_found_users(self, users_found_set:set, session:AsyncSession, date_added:arrow.arrow.Arrow):
        '''
        queries the database for all of the users found in the set


        if we are using postgres, we can update the database using a special insert statement that has
        'on conflict do nothing' (an "upsert")

        see https://docs.sqlalchemy.org/en/14/dialects/postgresql.html#insert-on-conflict-upsert

        but that requires us dropping down to `core`, so i'm doing it the hard way

        where we ask for all of the users and then diff them
        '''

        select_statement = select(db_model.FAUsersFound) \
            .filter(db_model.FAUsersFound.user_name.in_(users_found_set))

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

        for iter_user_name in users_not_in_db_set:
            session.add(db_model.FAUsersFound(date_added=date_added, user_name=iter_user_name))

    def does_submission_exist(self, current_fa_submission:model.FASubmission) -> bool:
        ''' returns whether the submission exists or not depending on the html

        '''

        result = current_fa_submission.soup.select("div.section-body")

        if result:

            result_element = result[0]

            if result_element.text.strip() == constants.SUBMISSION_DOESNT_EXIST_TEXT:
                logger.debug("submission `%s` doesn't exist", current_fa_submission)
                return False
            else:
                logger.debug("submission `%s`, does exist", current_fa_submission)
                return True
        else:

            logger.debug("didn't get a result back, assuming submission `%s` exists", current_fa_submission)
            return True


    def scrape_html(self, fa_submission):


        users_found_set = set()

        for iter_query in self.html_queries_list:

            result_set = set(iter_query.func(fa_submission.soup))

            # ogger.debug("query `%s` returned `%s` new users", iter_query.description, len(result_set))
            logger.debug("scrape_html: query `%s` returned `%s` unique users: `%s`", iter_query.description, len(result_set), result_set)


            # `update` only works on a set
            users_found_set.update(result_set)

        logger.info("found `%s` users for FA submission `%s`", len(users_found_set), fa_submission)

        return users_found_set

    def add_webpage_data_to_db(self, sqla_session, fa_submission, current_date):

        compress_and_hash_result = utils.compress_and_hash_text_data(fa_submission.raw_html)

        submission_wp = db_model.SubmissionWebPage(
            date_visited=current_date,
            submission_id=self.current_submission_counter,
            webpage_data=compress_and_hash_result.compressed_data,
            original_data_sha512=compress_and_hash_result.original_data_sha512,
            compressed_data_sha512=compress_and_hash_result.compressed_data_sha512)

        sqla_session.add(submission_wp)

    async def one_iteration(self, aiohttp_session, sessionmaker):

        async with sessionmaker() as sqla_session:

            # get things from the queue
            async with sqla_session.begin():

                current_date = arrow.utcnow()

                # get the current submission counter if we don't have it already
                if self.current_submission_counter == -1:
                    maybe_queue_row = await self.get_latest_item_from_submission_counter(sqla_session)

                    if not maybe_queue_row:
                        # don't have any submissions in the database, start with the first one
                        self.current_submission_counter = 1
                    else:
                        self.current_submission_counter = maybe_queue_row[0].submission_id + 1


                current_fa_submission = model.FASubmission(
                    submission_id=self.current_submission_counter,
                    raw_html=None,
                    soup=None,
                    does_exist=None)
                logger.info("on submission `%s`", current_fa_submission)

                # now get the webpage
                url = furl(constants.FURAFFINITY_URL_SUBMISSION.format(self.current_submission_counter))
                html_str = await utils.fetch_url(aiohttp_session, url)
                logger.debug("length of html: `%s`", len(html_str))
                soup = BeautifulSoup(html_str, "lxml")
                current_fa_submission = attr.evolve(current_fa_submission, raw_html=html_str, soup=soup)

                # see if the submission exists
                does_submission_exist = self.does_submission_exist(current_fa_submission)
                current_fa_submission = attr.evolve(current_fa_submission, does_exist=does_submission_exist)

                # if the submission does exist, save it in the database and scrape it for users
                # if it doesn't exist, don't do anything
                if does_submission_exist:

                    logger.info("submission `%s` exists, scraping html", current_fa_submission)

                    users_found_set = self.scrape_html(current_fa_submission)

                    # add the users to the database that we don't already have
                    await self.update_or_ignore_found_users(users_found_set, sqla_session, current_date)

                    # add the submission page data
                    self.add_webpage_data_to_db(sqla_session, current_fa_submission, current_date)

                else:

                    logger.info("submission `%s` doesn't exist, not searching for users", current_fa_submission)

                # set the new submission counter +1 in the database
                new_counter = db_model.SubmissionCounter(
                    submission_id=self.current_submission_counter,
                    date_visited=current_date,
                    submission_status=model.SubmissionStatus.EXISTS if current_fa_submission.does_exist else model.SubmissionStatus.DELETED)
                logger.info("adding new submission counter object to db: `%s`", new_counter)
                sqla_session.add(new_counter)
                self.current_submission_counter += 1

                # one with this FA submission
                logger.info("finished with submission `%s`", current_fa_submission)

    async def run(self, parsed_args, stop_event):

        self.config = parsed_args.config
        self.sqla_engine = utils.setup_sqlalchemy_engine(self.config.sqla_url)
        self.stop_event = stop_event

        try:
            # expire_on_commit=False will prevent attributes from being expired
            # after commit.
            self.async_sessionmaker = sessionmaker(
                bind=self.sqla_engine, expire_on_commit=False, class_=AsyncSession
            )

            async with self.sqla_engine.begin() as conn:
                await conn.run_sync(db_model.CustomDeclarativeBase.metadata.create_all)

            cookie_dict = self.config.cookie_jar.as_aiohttp_cookie_dict()
            header_dict = self.config.header_jar.as_aiohttp_header_dict()
            async with aiohttp.ClientSession(cookies=cookie_dict, headers=header_dict) as aiohttp_session:

                await utils.log_aiohttp_sessions_and_cookies(aiohttp_session)

                while not self.stop_event.is_set():
                    await self.one_iteration(aiohttp_session, self.async_sessionmaker)
                    await asyncio.sleep(4)


                logger.info("loop ended, returning")

        except Exception as e:
            logger.exception("uncaught exception")
            return

        finally:
            # make sure we dispose the engine because its not in an `async with` block
            await self.sqla_engine.dispose()
            self.sqla_engine = None

