import logging
import asyncio
import pathlib

import arrow
import aiofiles
import aiofiles.tempfile

from furaffinity_scrape import model
from furaffinity_scrape import db_model
from furaffinity_scrape import constants
from furaffinity_scrape import utils

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

    @staticmethod
    def get_wget_args_for_fa_submission(
        fa_scrape_attempt: db_model.FAScrapeAttempt,
        config:model.Settings,
        temp_dir:pathlib.Path,
        warc_file_without_ext:pathlib.Path) -> list[str]:

        submission_id = fa_scrape_attempt.furaffinity_submission_id
        current_date = arrow.utcnow().isoformat()
        cookie_path = config.temp_folder / "cookies.txt"
        temp_file = temp_dir / "wget.tmp"
        arg_list = [
            config.wget_path,
            f"--load-cookies={cookie_path}",
            "--span-hosts",
            "--page-requisites",
            "--no-check-certificate",
            "--no-warc-compression",
            f"--output-document={temp_file}",
            # "--warc-cdx",
            "--warc-header",
            "operator: Mark Grandi",
            "--warc-header",
            f"date: {current_date}",
            "--warc-header",
            f"furaffinity_submission: {submission_id}",
            "--warc-file",
            warc_file_without_ext,
            f"https://www.furaffinity.net/view/{submission_id}/"
        ]

        return arg_list

    @staticmethod
    async def download_submission_using_wget(
        fa_scrape_attempt:db_model.FAScrapeAttempt,
        config:model.Settings):

        async with aiofiles.tempfile.TemporaryDirectory(
            dir=config.temp_folder,
            prefix=f"fa_item_{fa_scrape_attempt.furaffinity_submission_id}_") as d:

            logger.debug("download_submission_using_wget: temporary directory is `%s`", d)

            temp_folder = pathlib.Path(d)

            warc_file_path_with_ext = temp_folder / f"fascrape_submission_{fa_scrape_attempt.furaffinity_submission_id}.warc"

            # run wget

            wget_args = FileUtils.get_wget_args_for_fa_submission(
                fa_scrape_attempt=fa_scrape_attempt,
                config=config,
                temp_dir=temp_folder,
                warc_file_without_ext=warc_file_path_with_ext.with_suffix(""))

            logger.debug("wget args: `%s`", wget_args)


            try:

                stdout_output = await utils.run_command_and_wait(
                    binary_to_run=config.wget_path,
                    argument_list=wget_args,
                    timeout=5,
                    acceptable_return_codes=[0,1],
                    cwd=None)

                breakpoint()
            except Exception as e:
                logger.error("Failed to run wget")
                raise Exception("Failed to run wget") from e

            logger.debug("wget command finished")






