import logging

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

        pass


    def run(self, parsed_args):

        logger.info("parsed args were: `%s`", parsed_args)