from __future__ import annotations
import logging
import typing

import aiohttp
from furl import furl
import arrow
from sqlalchemy import select, desc
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession

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

        self.config = None
        self.sqla_engine = None
        self.async_sessionmaker = None
        self.current_submission_counter = -1


    async def get_latest_item_from_submission_counter(self, session:AsyncSession) -> typing.Optional[db_model.SubmissionCounter]:

        logger.debug("fetching one row from SubmissionCounter ")
        stmt = select(db_model.SubmissionCounter).order_by(desc("submission_id")).limit(1)

        res = await session.execute(stmt)

        logger.debug("SubmissionCounter result: `%s`", res)

        return res.one_or_none()

    async def fetch_url(self, session, url:furl.furl) -> str:

        logger.debug("making request to `%s`", url)
        async with session.get(url.url) as response:

            logger.debug("request to `%s` resulted in: `%s`", url, response.status)

            async with response:
                response.raise_for_status()

                return await response.text()

    async def run(self, parsed_args):

        self.config = parsed_args.config
        self.sqla_engine = utils.setup_sqlalchemy_engine(self.config.sqla_url)


        # expire_on_commit=False will prevent attributes from being expired
        # after commit.
        self.async_sessionmaker = sessionmaker(
            bind=self.sqla_engine, expire_on_commit=False, class_=AsyncSession
        )

        async with self.sqla_engine.begin() as conn:
            await conn.run_sync(db_model.CustomDeclarativeBase.metadata.create_all)

        async with aiohttp.ClientSession() as aiohttp_session:
            async with self.async_sessionmaker() as session:

                # get things from the queue
                async with session.begin():

                    maybe_queue_row = await self.get_latest_item_from_submission_counter(session)

                    if not maybe_queue_row:
                        # don't have any submissions in the database, start with the first one
                        self.current_submission_counter = 1
                    else:
                        self.current_submission_counter = maybe_queue_row.submission_counter_id


                    # now get the webpage
                    url = furl(constants.FURAFFINITY_URL_SUBMISSION.format(self.current_submission_counter))

                    html_str = await self.fetch_url(aiohttp_session, url)
                    breakpoint()

                    logger.info("here")



