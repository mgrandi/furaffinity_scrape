from __future__ import annotations
import logging
import typing
import asyncio
import asyncio.subprocess
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


        # first, read the data from disk so we aren't doing it multiple times
        sevenzip_decompressed_data = await self._read_sevenzip_data(item.file_path)

        # get the warcat rows

        warc_records = await self.get_warc_record_list(sevenzip_decompressed_data)

        warcinfo_record = self._find_first_warc_record_matches_function(lambda x: x.warc_type == "warcinfo", warc_records)

        headers_ba = await self._get_decoded_base64_for_warcrecord(sevenzip_decompressed_data, warcinfo_record)
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


    async def _read_sevenzip_data(self, path:pathlib.Path) -> bytearray:

        cmd = self.config.sevenzip_path
        args = ["x", "-so", path]
        proc = await asyncio.create_subprocess_exec(cmd, *args, stdout=asyncio.subprocess.PIPE)

        result_tuple =  await proc.communicate()

        return result_tuple[0]

    async def run_warcat_command(self, warc_data:bytearray,warcat_args:list[str]) -> bytearray:

        proc = await asyncio.create_subprocess_exec(
            self.warcat_path,
            *warcat_args,
            stdin=asyncio.subprocess.PIPE,
            stdout=asyncio.subprocess.PIPE)
        result_tuple = await proc.communicate(warc_data)

        return result_tuple[0]


    async def get_warc_record_list(self, data:bytearray) -> list[model.WarcatRecordInformation]:

        warcat_args = ["--quiet", "list", "--input",
            "-", "--compression", "none",  "--format", "jsonl", "--field",
            ":position,WARC-Record-ID,WARC-Type,Content-Type,WARC-Target-URI"]

        raw_data = await self.run_warcat_command(warc_data=data, warcat_args=warcat_args)

        sio = io.StringIO(raw_data.decode("utf-8"))


        result_list = list()
        while True:
            iter_line = sio.readline()
            if not iter_line:
                break

            json_line = json.loads(iter_line)
            info = model.WarcatRecordInformation(
                position=json_line[0],
                warc_record_id=json_line[1],
                warc_type=json_line[2],
                content_type=json_line[3],
                warc_target_uri=json_line[4])

            result_list.append(info)

        return result_list




    async def _get_decoded_base64_for_warcrecord(self, data:bytearray, warcrecord:model.WarcatRecordInformation) -> bytearray:

        warcat_args = [
            "--quiet",
            "get", "export",
            "--input", "-",
            "--compression", "none",
            "--format", "jsonl",
            "--position", f"{warcrecord.position}",
            "--id", warcrecord.warc_record_id]

        result_bytes = await self.run_warcat_command(
            warc_data=data, warcat_args=warcat_args)

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





