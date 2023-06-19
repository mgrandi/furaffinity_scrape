import logging
import asyncio
import pathlib

import aiofiles
import aiofiles.tempfile

from furaffinity_scrape import model
from furaffinity_scrape import db_model
from furaffinity_scrape import constants

logger = logging.getLogger(__name__)

class FileUtils:

    @staticmethod
    def write_cookie_file(config:model.Settings):


        with open(config.cookie_path, "w", encoding="utf-8") as f:
            f.write("# Netscape HTTP Cookie File\n")

            for k,v in config.cookie_jar.as_aiohttp_cookie_dict().items():

                f.write(f".furaffinity.net\tTRUE\t/\tTRUE\t2147483646\t{k}\t{v}\n")

            # write anti cookie banner cookie
            f.write(f"www.furaffinity.net\tTRUE\t/\tTRUE\t2147483646\tcc\t1\n")

    # @staticmethod
    # def get_wget_args_for_fa_submission(fa_scrape_attempt: db_model.FAScrapeAttempt, config:model.Settings) -> list[str]:

    #     arg_list = [
    #         config.wget_path,
    #         ""
    #     ]

    # @staticmethod
    # async def download_submission_using_wget(fa_scrape_attempt:db_model.FAScrapeAttempt, config:model.Settings):

    #     async with aiofiles.tempfile.TemporaryDirectory(
    #         dir=config.temp_folder,
    #         prefix=f"fa_item_{fa_scrape_attempt.furaffinity_submission_id}_") as d:

    #         logger.debug("download_submission_using_wget: temporary directory is `%s`", d)

    #         # run wget

