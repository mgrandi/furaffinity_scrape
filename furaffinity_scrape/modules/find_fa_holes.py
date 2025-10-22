from __future__ import annotations
import logging
import typing
import asyncio
import pathlib
import subprocess
import json
import io
import base64
import re

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import sessionmaker
from sqlalchemy import select, desc, text

from furaffinity_scrape import utils
from furaffinity_scrape import db_model
from furaffinity_scrape import model
from furaffinity_scrape import constants
from furaffinity_scrape import html_utils
from furaffinity_scrape import file_utils

logger = logging.getLogger(__name__)

class FindFaHoles:


    @staticmethod
    def create_subparser_command(argparse_subparser):
        '''
        populate the argparse arguments for this module

        @param argparse_subparser - the object returned by ArgumentParser.add_subparsers()
        that we call add_parser() on to add arguments and such

        '''

        parser = argparse_subparser.add_parser("find_fa_holes")

        # adding it here rather than in the config because as far as i know only one module needs this
        # and i am manually running it on a single machine
        parser.add_argument("--warcat-path",
            dest="warcat_path",
            type=utils.isFileType(True),
            required=True,
            help="path to warcat")

        hole_obj = FindFaHoles()

        # set the function that is called when this command is used
        parser.set_defaults(func_to_run=hole_obj.run)


    def __init__(self):

        self.config = None
        self.stop_event = None
        self.sqla_engine = None
        self.warcat_path = None

        self.fa_url_regex = re.compile("")

    async def run(self, parsed_args, stop_event):


        self.stop_event = stop_event
        self.config = parsed_args.config
        self.sqla_engine = utils.setup_sqlalchemy_engine(self.config.sqla_url)

        # expire_on_commit=False will prevent attributes from being expired
        # after commit.
        self.async_sessionmaker = sessionmaker(
            bind=self.sqla_engine, expire_on_commit=False, class_=AsyncSession
        )

        self.warcat_path = parsed_args.warcat_path

        while True:

            if self.stop_event.is_set():
                logger.info("stop event is set, breaking out early")
                break

            async with self.async_sessionmaker() as sqla_session:


                # pick out one unfinished row
                query = select(db_model.FuraffinityHoleStatus)\
                    .where(db_model.FuraffinityHoleStatus.processed_status == model.ProcessedStatus.TODO)\
                    .limit(1)

                query_result = await sqla_session.execute(query)
                query_result_list = query_result.all()

                logger.debug("query result got `%s` rows back", len(query_result_list) )

                if len(query_result_list) == 0:
                    logger.info("got 0 rows back, seems to be no more processed rows, breaking out")

                    stop_event.signal()
                    continue

                for iter_row in query_result_list:
                    # a sequence of row objects, we want the row
                    await self.handle_one_row(iter_row[0])





    async def handle_one_row(self, item:db_model.FuraffinityHoleStatus):

        # call warcat / 7z to see if it is there

        item_path = pathlib.Path(item.file_path)


        logger.debug("handling row `%s`", item)



        warc_records = self.get_warc_record_list(item_path)

        warcinfo_record = self._find_first_warc_record_matches_function(lambda x: x.warc_type == "warcinfo", warc_records)

        headers_ba = self._get_decoded_base64_for_warcrecord(warcinfo_record)
        headers_dict = self._get_warcinfo_header_dict_from_bytearray(headers_ba)

        breakpoint()


    def _get_warcinfo_header_dict_from_bytearray(
        self,
        ba:bytearray) -> dict:

        sio = io.StringIO(ba.decode("utf-8"))

        result_dict = dict()
        while True:
            iter_line = sio.readline().strip()
            if not iter_line:
                break

            if ":" not in iter_line:
                logger.debug("skipping invalid header line `%s`", iter_line)
                continue

            key, value = iter_line.split(":", maxsplit=1)
            result_dict[key] = value


        return result_dict


    def _find_first_warc_record_matches_function(
        self,
        fn,
        record_list:list[model.WarcatRecordInformation]) -> model.WarcatRecordInformation|None:

        for iter_record in record_list:
            if fn(iter_record):
                return iter_record

        # didn't find any matches
        return None



    def get_warc_record_list(self, warc_file_path:pathlib.Path) -> list[model.WarcatRecordInformation]:

        warcat_args = ["--quiet", "list", "--input",
            "-", "--compression", "none",  "--format", "jsonl", "--field",
            ":position,WARC-Record-ID,WARC-Type,Content-Type,WARC-Target-URI"]

        result_bytes = self.run_warcat_command(
            self.config.sevenzip_path,
            self.warcat_path,
            warc_file_path,
            warcat_args)

        sio = io.StringIO(result_bytes.decode("utf-8"))

        result_list = list()
        while True:
            iter_line = sio.readline()
            if not iter_line:
                break

            json_line = json.loads(iter_line)
            info = model.WarcatRecordInformation(
                warc_filepath=warc_file_path,
                position=json_line[0],
                warc_record_id=json_line[1],
                warc_type=json_line[2],
                content_type=json_line[3],
                warc_target_uri=json_line[4])

            result_list.append(info)

        return result_list




    def _get_decoded_base64_for_warcrecord(self, warcrecord:model.WarcatRecordInformation) -> bytearray:

        warcat_args = [
            "--quiet",
            "get", "export",
            "--input", "-",
            "--compression", "none",
            "--format", "jsonl",
            "--position", f"{warcrecord.position}",
            "--id", warcrecord.warc_record_id]

        result_bytes = self.run_warcat_command(
            self.config.sevenzip_path,
            self.warcat_path,
            warcrecord.warc_filepath,
            warcat_args)

        sio = io.StringIO(result_bytes.decode("utf-8"))
        ba = bytearray()
        while True:
            iter_line = sio.readline()
            if not iter_line:
                break

            json_line = json.loads(iter_line)
            if "ExtractMetadata" in json_line:
                continue
            if "BlockChunk" in json_line:
                ba.extend(base64.b64decode(json_line["BlockChunk"]["data"]))
        return ba



    def run_warcat_command(self,
        sevenzip_path:pathlib.Path,
        warcat_path:pathlib.Path,
        warc_file:pathlib.Path,
        warcat_arguments:list[str]) -> str:


        sevenzip_args = [sevenzip_path, "x", "-so", warc_file]

        warcat_args = [warcat_path]
        warcat_args.extend(warcat_arguments)

        logger.debug("running warcat command: `%s`", warcat_args)

        with subprocess.Popen(sevenzip_args, stdout=subprocess.PIPE, close_fds=False) as seven_zip_process:

            warcat_process = subprocess.Popen(warcat_args, stdin=seven_zip_process.stdout, stdout=subprocess.PIPE)

            # you have to close the pipe to make it work or else it seems to just truncate it part way?
            # no idea what is actually happening here
            # https://stackoverflow.com/questions/13332268/how-to-use-subprocess-command-with-pipes
            seven_zip_process.stdout.close()
            warcat_stdout, warcat_stderr = warcat_process.communicate()


            return warcat_stdout




