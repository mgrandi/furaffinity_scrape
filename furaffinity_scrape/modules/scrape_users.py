from __future__ import annotations
import logging

from furaffinity_scrape import utils

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

    def run(self, parsed_args):

        self.config = parsed_args.config
        self.sqla_engine = utils.setup_sqlalchemy_engine(self.config.sqla_url)


