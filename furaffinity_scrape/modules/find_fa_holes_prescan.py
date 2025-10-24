from __future__ import annotations
import logging
import typing
import asyncio
import pathlib

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker

from furaffinity_scrape import utils
from furaffinity_scrape import db_model
from furaffinity_scrape import model
from furaffinity_scrape import constants
from furaffinity_scrape import html_utils
from furaffinity_scrape import file_utils

logger = logging.getLogger(__name__)

class FindFaHolesPrescan:


    @staticmethod
    def create_subparser_command(argparse_subparser):
        '''
        populate the argparse arguments for this module

        @param argparse_subparser - the object returned by ArgumentParser.add_subparsers()
        that we call add_parser() on to add arguments and such

        '''

        parser = argparse_subparser.add_parser("find_fa_holes_prescan")

        parser.add_argument("--rootdir",
            dest="rootdir",
            type=utils.isDirectoryType,
            required=True,
            help="the path to the folder where we will scan for submissions")

        parser.add_argument("--run-id",
            dest="run_id",
            type=int,
            required=True,
            help="the run identifier in case we want to do multiple runs")

        hole_obj = FindFaHolesPrescan()

        # set the function that is called when this command is used
        parser.set_defaults(func_to_run=hole_obj.run)


    def __init__(self):

        self.config = None
        self.stop_event = None
        self.sqla_engine = None
        self.async_sessionmaker = None

    async def run(self, parsed_args, stop_event):

        self.stop_event = stop_event
        self.config = parsed_args.config
        self.sqla_engine = utils.setup_sqlalchemy_engine(self.config.sqla_url)
        # expire_on_commit=False will prevent attributes from being expired
        # after commit.
        self.async_sessionmaker = sessionmaker(
            bind=self.sqla_engine, expire_on_commit=False, class_=AsyncSession
        )


        run_id = parsed_args.run_id
        root_directory = parsed_args.rootdir

        logger.info("starting scan at `%s`", root_directory)

        for dirpath, dirnames, filenames in root_directory.walk(top_down=True):

            if self.stop_event.is_set():
                logger.info("stop event is set, breaking out early at folder `%s`", dirpath)
                break

            async with self.async_sessionmaker() as sqla_session:

                logger.info("on directory `%s`, we have `%s` files", dirpath, len(filenames))

                async with sqla_session.begin():
                    for iter_file in filenames:

                        current_file = dirpath / iter_file

                        self.handle_iter_file(run_id, current_file, sqla_session)

                    logger.info("Committing...")

        logger.info("done!")


    def handle_iter_file(self, run_id:int, current_file:pathlib.Path, session:AsyncSession):


        # create database object
        dbobj = db_model.FuraffinityHoleStatus(
            run_id=run_id,
            processed_status=model.ProcessedStatus.TODO,
            file_path=str(current_file),
            warc_sha512=None,
            fa_submission_status=model.FuraffinitySubmissionStatus.UNKNOWN)

        # add it to the session
        session.add(dbobj)






