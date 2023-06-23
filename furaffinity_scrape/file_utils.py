import logging
import asyncio
import pathlib
import typing
import hashlib

import arrow
import aiofiles
import aiofiles.tempfile
import aiofiles.os
import bitmath

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
        warc_tempdir = temp_dir / "warc_temp_folder"


        arg_list = [
            config.wget_path,
            f"--load-cookies={cookie_path}",
            "-e",
            "robots=off",
            "--user-agent",
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:109.0) Gecko/20100101 Firefox/116.0",
            "--span-hosts",
            "--page-requisites",
            "--no-check-certificate",
            "--no-warc-compression",
            "--warc-tempdir",
            f"{warc_tempdir}",
            # "--warc-cdx", # this causes wpull to error out?
            "--warc-header",
            "operator: Mark Grandi",
            "--warc-header",
            f"date: {current_date}",
            "--warc-header",
            f"furaffinity_submission: {submission_id}",
            "--warc-header",
            f"script_version: {config.git_describe_string}",
            "--warc-file",
            warc_file_without_ext,
            "--recursive",
            "--level",
            "1",
            "--accept-regex",
            constants.WGET_ACCEPT_REGEX,
            f"https://www.furaffinity.net/view/{submission_id}/"
        ]

        return arg_list

    @staticmethod
    async def download_submission_using_wget(
        fa_scrape_attempt:db_model.FAScrapeAttempt,
        config:model.Settings) -> db_model.FAScrapeContent:

        async with aiofiles.tempfile.TemporaryDirectory(
            dir=config.temp_folder,
            prefix=f"fa_item_{fa_scrape_attempt.furaffinity_submission_id}_") as d:

            logger.debug("download_submission_using_wget: temporary directory is `%s`", d)

            temp_folder = pathlib.Path(d)

            wget_tempdir = temp_folder / "wget_tempdir"
            wget_tempdir.mkdir()

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
                    acceptable_return_codes=constants.WGET_EXPECTED_RETURN_CODES,
                    cwd=wget_tempdir)

            except Exception as e:
                logger.error("Failed to run wget")
                raise Exception("Failed to run wget") from e

            logger.debug("wget command finished")

            # now load the file into memory

            fa_scrape_content = await FileUtils.compress_warc_file(
                warc_file_to_compress=warc_file_path_with_ext,
                settings=config)

            fa_scrape_content.attempt = fa_scrape_attempt

            return fa_scrape_content

    @staticmethod
    async def compress_warc_file(
        warc_file_to_compress:pathlib.Path,
        settings:model.Settings) -> db_model.FAScrapeContent:

        original_file_stat = await aiofiles.os.stat(warc_file_to_compress)
        original_file_size = original_file_stat.st_size
        original_file_size_string = bitmath.Byte(original_file_size).best_prefix().format(constants.BITMATH_FORMATTING_STRING)

        compressed_warc_filepath = warc_file_to_compress.with_suffix(warc_file_to_compress.suffix + ".7z")

        sevenzip_compress_arg_list = [
            "a",                                    # add to archive
            "-t7z",                                 # 7z file type
            "-bd",                                  # disable progress indicator
            "-r",                                   # recurse
            "-mx=9",                                # compression level 9
            compressed_warc_filepath,                 # resulting archive file path
            warc_file_to_compress
        ]

        try :
            logger.debug("Compressing `%s` with 7z", warc_file_to_compress)

            sevenzip_stdout = await utils.run_command_and_wait(
                binary_to_run=settings.sevenzip_path,
                argument_list=sevenzip_compress_arg_list,
                timeout=5,
                acceptable_return_codes=constants.SEVENZIP_EXPECTED_RETURN_CODES,
                cwd=warc_file_to_compress.parent)

        except Exception as e:

            logger.exception("Failed to compress warc file `%s`", warc_file_to_compress)
            raise e

        hasher = hashlib.sha512()
        content_length = 0
        content_bytes = bytearray()

        # now load the file that was created
        async with aiofiles.open(compressed_warc_filepath, "rb") as compressed_warc_fileobj:

            # read the 7z file into memory and hash it
            while True:

                iter_data = await compressed_warc_fileobj.read(64 * 1024)

                if not iter_data:
                    break

                hasher.update(iter_data)
                content_length += len(iter_data)
                content_bytes += iter_data


        compressed_file_size_string = bitmath.Byte(content_length).best_prefix().format(constants.BITMATH_FORMATTING_STRING)

        logger.info("Compressed `%s` (`%s` -> `%s`)",
            warc_file_to_compress.name, original_file_size_string, compressed_file_size_string)

        scrape_content = db_model.FAScrapeContent(
            content_length=content_length,
            content_sha512=hasher.hexdigest(),
            content_binary=content_bytes)

        return scrape_content







