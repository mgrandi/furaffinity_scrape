import logging
import json
import asyncio
import pathlib

import aio_pika

import arrow
from sqlalchemy import select, desc, text, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from furaffinity_scrape import utils
from furaffinity_scrape import db_model

logger = logging.getLogger(__name__)

class ExtractFilesFromDb:


    @staticmethod
    def create_subparser_command(argparse_subparser):
        '''
        populate the argparse arguments for this module

        @param argparse_subparser - the object returned by ArgumentParser.add_subparsers()
        that we call add_parser() on to add arguments and such

        '''

        parser = argparse_subparser.add_parser("extract_files_from_db")

        extract_files_from_db = ExtractFilesFromDb()

        # set the function that is called when this command is used
        parser.set_defaults(func_to_run=extract_files_from_db.run)


    def __init__(self):

        self.config = None

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

            number_of_rows = 0
            async with self.async_sessionmaker() as sqla_session:

                # select_statement = select(db_model.User) \
                # .filter(db_model.User.user_name.in_(users_found_set))

                select_statement = select(func.count()).select_from(db_model.FAScrapeContent) \
                    .filter(db_model.FAScrapeContent.content_binary != None)
                select_result = await sqla_session.execute(select_statement)
                number_of_rows = select_result.scalars().all()[0]

            logger.info("number of rows: `%s`", number_of_rows)


            for i in range(0, number_of_rows):

                if self.stop_event.is_set():
                    logger.info("Stop event is set, breaking")
                    break

                async with self.async_sessionmaker() as sqla_session:

                    async with sqla_session.begin():

                        stmt = select(db_model.FAScrapeContent).filter(db_model.FAScrapeContent.content_binary != None).limit(5)

                        select_result = await sqla_session.execute(stmt)

                        results = select_result.all()



                        for iter_row in results:

                            for single_result in iter_row:

                                # see if we already deleted it
                                if len(single_result.content_binary) == 0:
                                    # set it to be null and continue
                                    logger.info("`%s` already had it's content deleted, setting it to null and continuing", iter_row)
                                    single_result.content_binary = None
                                    continue


                                folder = pathlib.Path("/mnt/g/fascrape/")
                                sha_prefix_folder_name = single_result.content_sha512[0:3]
                                full_folder_name = folder / sha_prefix_folder_name

                                # create the folder if it doesn't exist
                                if not full_folder_name.exists():
                                    logger.info("Creating folder `%s`", full_folder_name)
                                    full_folder_name.mkdir()


                                filename = full_folder_name / f"fascrape_content_cid-{single_result.content_id}_aid-{single_result.attempt_id}.tar.xz"
                                with open(filename, "wb") as f:
                                    f.write(single_result.content_binary)

                                logger.info("wrote `%s` bytes to `%s`", len(single_result.content_binary), filename)

                                single_result.content_binary = None

                        logger.debug("Committing...")



        except Exception as e:
            logger.exception("uncaught exception")
            await self.close_stuff()
            raise e

        await self.close_stuff()


    async def close_stuff(self):

        # make sure we dispose the engine because its not in an `async with` block

        if self.sqla_engine:
            logger.info("closing sqla engine")
            await self.sqla_engine.dispose()
            self.sqla_engine = None
