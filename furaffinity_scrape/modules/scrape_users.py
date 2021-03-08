from __future__ import annotations
import logging
import typing
import asyncio

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

        self.stop_event = None
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

            response.raise_for_status()

            return await response.text()

    async def loop(self, aiohttp_session, sessionmaker):

        async with sessionmaker() as sqla_session:

            # get things from the queue
            async with sqla_session.begin():

                # get the current submission counter if we don't have it already
                if self.current_submission_counter == -1:
                    maybe_queue_row = await self.get_latest_item_from_submission_counter(sqla_session)

                    if not maybe_queue_row:
                        # don't have any submissions in the database, start with the first one
                        self.current_submission_counter = 1
                    else:
                        self.current_submission_counter = maybe_queue_row[0].submission_id + 1

                logger.info("on submission counter `%s`", self.current_submission_counter)

                # now get the webpage
                url = furl(constants.FURAFFINITY_URL_SUBMISSION.format(self.current_submission_counter))

                html_str = await self.fetch_url(aiohttp_session, url)
                logger.info("length of html: `%s`", len(html_str))

                # set the new submission counter +1
                new_counter = db_model.SubmissionCounter(submission_id=self.current_submission_counter)
                logger.info("adding new submission counter object to db: `%s`", new_counter)
                sqla_session.add(new_counter)
                self.current_submission_counter += 1

                logger.info("committing")

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

            async with aiohttp.ClientSession() as aiohttp_session:

                while not self.stop_event.is_set():
                    await self.loop(aiohttp_session, self.async_sessionmaker)
                    await asyncio.sleep(4)


                logger.info("loop ended, returning")

        except Exception as e:
            logger.exception("uncaught exception")
            return

        finally:
            # make sure we dispose the engine because its not in an `async with` block
            await self.sqla_engine.dispose()
            self.sqla_engine = None

