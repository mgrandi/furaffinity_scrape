import logging
import logging.config
import argparse
import sys
import asyncio

import logging_tree

from furaffinity_scrape import utils
from furaffinity_scrape.modules.scrape_users import ScrapeUsers
from furaffinity_scrape.modules.populate_rabbit import PopulateRabbit

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

        root_logger = logging.getLogger()

        try:

            # set up logging stuff
            logging.captureWarnings(True) # capture warnings with the logging infrastructure

            parsed_args = parser.parse_args()

            logging.config.dictConfig(parsed_args.config.logging_config)

            root_logger.info("starting")

            root_logger.debug("Parsed arguments: %s", parsed_args)
            root_logger.debug("Logger hierarchy:\n%s", logging_tree.format.build_description(node=None))

            # register Ctrl+C/D/whatever signal
            def _please_stop_loop_func():
                root_logger.info("setting stop event")
                self.stop_event.set()

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

