import logging
import logging.config
import argparse
import sys
import asyncio
import logging_tree
import actorio

from furaffinity_scrape import utils
from furaffinity_scrape.modules.scrape_users import ScrapeUsers
from furaffinity_scrape.modules.scrape_submissions import ScrapeSubmissions
from furaffinity_scrape.modules.populate_rabbit import PopulateRabbit
from furaffinity_scrape.modules.extract_files_from_db import ExtractFilesFromDb
from furaffinity_scrape.modules.queue_latest_submissions import QueueLatestSubmissions



def start():
    m = Main()
    asyncio.run(m.run(), debug=False)


class Main():

    def __init__(self):

        # DON'T CREATE THIS NOW
        # you have to create it once the event loop is running (aka asyncio.run() gets called with the `run` method below)
        # or else you get "got Future <Future pending> attached to a different loop" errors
        self.stop_event = None


    async def run(self):

        self.stop_event = asyncio.Event()

        parser = argparse.ArgumentParser(
            description="utilities for scraping furaffinity.net",
            epilog="Copyright 2021-02-23 - Mark Grandi",
            fromfile_prefix_chars='@')

        parser.add_argument("--config",
            dest="config",
            required=True,
            type=utils.parse_config,
            help="the HOCON config file")

        # ScrapeUsers command
        subparsers = parser.add_subparsers()
        ScrapeUsers.create_subparser_command(subparsers)

        # PopulateRabbit command
        PopulateRabbit.create_subparser_command(subparsers)

        # ScrapeSubmissions command
        ScrapeSubmissions.create_subparser_command(subparsers)

        ExtractFilesFromDb.create_subparser_command(subparsers)

        QueueLatestSubmissions.create_subparser_command(subparsers)

        root_logger = logging.getLogger()

        try:


            parsed_args = parser.parse_args()

            logging.config.dictConfig(parsed_args.config.logging_config)
            logging.captureWarnings(True) # capture warnings with the logging infrastructure

            root_logger.info("starting")

            root_logger.debug("Parsed arguments: %s", parsed_args)
            root_logger.debug("Logger hierarchy:\n%s", logging_tree.format.build_description(node=None))

            # register Ctrl+C/D/whatever signal
            def _please_stop_loop_func():
                root_logger.info("setting stop event: %s", self.stop_event)

                # this is complex now because it wasn't working before
                # see https://stackoverflow.com/questions/48836285/python-asyncio-event-wait-not-responding-to-event-set
                asyncio.get_running_loop().call_soon_threadsafe(self.stop_event.set)

            utils.register_ctrl_c_signal_handler(_please_stop_loop_func)

            # run the function associated with each sub command
            if "func_to_run" in parsed_args:
                await parsed_args.func_to_run(parsed_args, self.stop_event)

                # await to let aiohttp close its connection
                await asyncio.sleep(0.5)

            else:
                root_logger.info("no subcommand specified!")
                parser.print_help()
                sys.exit(0)

            root_logger.info("Done!")
        except Exception as e:
            root_logger.exception("Something went wrong!")
            sys.exit(1)

