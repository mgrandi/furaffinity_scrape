import logging
import argparse
import sys
import asyncio

import logging_tree

from furaffinity_scrape import utils
from furaffinity_scrape.modules.scrape_users import ScrapeUsers


async def main():

    parser = argparse.ArgumentParser(
        description="utilities for scraping furaffinity.net",
        epilog="Copyright 2021-02-23 - Mark Grandi",
        fromfile_prefix_chars='@')


    parser.add_argument("--log-to-file-path",
        dest="log_to_file_path",
        type=utils.isFileType(False),
        help="log to the specified file")
    parser.add_argument("--no-stdout",
        dest="no_stdout",
        action="store_true",
        help="if true, will not log to stdout")
    parser.add_argument("--verbose",
        action="store_true",
        help="Increase logging verbosity")

    parser.add_argument("--config",
        dest="config",
        required=True,
        type=utils.parse_config,
        help="the HOCON config file")

    # ScrapeUsers command
    subparsers = parser.add_subparsers()
    ScrapeUsers.create_subparser_command(subparsers)

    try:

        # set up logging stuff
        logging.captureWarnings(True) # capture warnings with the logging infrastructure
        root_logger = logging.getLogger()
        logging_formatter = utils.ArrowLoggingFormatter("%(asctime)s %(threadName)-10s %(name)-30s %(levelname)-8s: %(message)s")

        parsed_args = parser.parse_args()


        if parsed_args.log_to_file_path:

            file_handler = logging.FileHandler(
                parsed_args.log_to_file_path,
                encoding="utf-8")
            file_handler.setFormatter(logging_formatter)
            root_logger.addHandler(file_handler)

        if not parsed_args.no_stdout:
            logging_handler = logging.StreamHandler(sys.stdout)
            logging_handler.setFormatter(logging_formatter)
            root_logger.addHandler(logging_handler)


        # set logging level based on arguments
        if parsed_args.verbose:
            root_logger.setLevel("DEBUG")
        else:
            root_logger.setLevel("INFO")

        root_logger.info("########### STARTING ###########")

        root_logger.debug("Parsed arguments: %s", parsed_args)
        root_logger.debug("Logger hierarchy:\n%s", logging_tree.format.build_description(node=None))


        # run the function associated with each sub command
        if "func_to_run" in parsed_args:

            await parsed_args.func_to_run(parsed_args)

        else:
            root_logger.info("no subcommand specified!")
            parser.print_help()
            sys.exit(0)

        root_logger.info("Done!")
    except Exception as e:
        root_logger.exception("Something went wrong!")
        sys.exit(1)

