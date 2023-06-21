import pathlib
import logging
import pyhocon
import argparse
import signal
import tarfile
import io
import hashlib
import asyncio
import subprocess
import socket
import os
from logging.handlers import TimedRotatingFileHandler

import yarl
import aiohttp
import arrow
import sqlalchemy
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.event import listen


from furaffinity_scrape import constants
from furaffinity_scrape.constants import HoconTypesEnum

from furaffinity_scrape import model

logger = logging.getLogger(__name__)


def get_identity_string():
    '''
    returns a string suitable for identifying this machine, PID and version of code running

    @return a string
    '''

    fqdn = socket.getfqdn()
    pid = os.getpid()
    git_describe_output = get_git_describe_output()
    identity_string = f"FQDN[{fqdn}]-PID[{pid}]-VER[{git_describe_output}]"

    return identity_string

def get_git_describe_output(abbreviate_hash_length=20):
    '''
    runs git describe on the root folder of the git repository

    note: this is kinda hacky, and relies on this being run inside the git repo

    @param abbreviate_hash_length the number of characters the git hash itself will be abbreviated to
    0 means no characters, 40 means the entire thing
    '''

    git_repo_path = pathlib.Path(__file__).joinpath("../../.git").resolve()

    # these arguments make it so that it will show the full commit hash + if it is dirty or not
    # even if there are no tags
    # if there is a tag, it will include it along with how many commits it is above that tag
    # examples:
    # `v0.1.0-5-g28074bff058fe6cdb73297cab09e2fd14ca3a9ca-dirty`
    # (after we remove that tag)
    # `28074bff058fe6cdb73297cab09e2fd14ca3a9ca-dirty`
    git_describe_args = [
        "git",
        "--git-dir",
        git_repo_path,
        "describe",
        "--tags",
        "--first-parent",
        f"--abbrev={abbreviate_hash_length}", # HAS to be on the same line or else you get `fatal: --dirty is incompatible with commit-ishes`
        "--long",
        "--always",
        "--dirty",
    ]

    logger.debug("describe args: `%s`", git_describe_args)

    git_describe_result = subprocess.run(git_describe_args, capture_output=True)

    stdout = git_describe_result.stdout.decode("utf-8").strip()
    logger.debug("git describe result: `%s`", stdout)
    return stdout

async def log_aiohttp_sessions_and_cookies(session:aiohttp.ClientSession):
    '''
    hits httpbin.org/anything with our currently configured ClientSession
    to get our headers and cookies
    '''

    httpbin_str_result = await fetch_url(session, yarl.URL(constants.HTTPBIN_URL))
    logger.debug("aiohttp ClientSession headers and cookies: `%s`", httpbin_str_result)

async def fetch_url(session:aiohttp.ClientSession, url:yarl.URL) -> model.AiohttpResponseResult:
    '''
    fetch a url with an aiohttp session
    '''

    for attempt_number in range(1, constants.FETCH_URL_MAX_ATTEMPTS + 1):
        try:
            logger.debug("fetch_url: attempt `%s`, making request to `%s", attempt_number, url)

            async with session.get(url) as response:

                logger.debug("fetch_url: attempt `%s`, request to `%s` resulted in: `%s`",
                    attempt_number, url, response.status)

                response.raise_for_status()

                result_bytes = await response.read()

                # some of the pages we are encountering are like a mix of encodings, the outer webpage is utf-8
                # but then the 'content' the user uploads is not utf-8 and that is causing a UnicodeDecodeError
                # when we call `response.text()`, so here we attempt to decode with utf8 and if we get an
                # exception, we try it again with `errors="backslashreplace"`, and we will later
                # insert it into the database and note that it decoded incorrectly
                try:

                    result_html = result_bytes.decode("utf-8")
                    return model.AiohttpResponseResult(
                        decoded_text=result_html,
                        binary_data=result_bytes,
                        encountered_decoding_error=False)

                except UnicodeDecodeError as e:

                    logger.warning("the bytes for url `%s` gave us a UnicodeDecodeError (`%s`), decoding with `errors=\"backslashreplace\"`",
                        url, e)

                    result_html = result_bytes.decode("utf-8", errors="backslashreplace")
                    return model.AiohttpResponseResult(
                        decoded_text=result_html,
                        binary_data=result_bytes,
                        encountered_decoding_error=True)

        except Exception as e:
            logger.error("fetch_url: attempt `%s`, Caught exception when making request to `%s`: `%s`",
                attempt_number, url, e)

            logger.debug("fetch_url: sleeping for `%s` seconds...",
                constants.FETCH_URL_TIME_TO_SLEEP_BETWEEN_ATTEMPTS_SECONDS)
            await asyncio.sleep(constants.FETCH_URL_TIME_TO_SLEEP_BETWEEN_ATTEMPTS_SECONDS)

    logger.error("Failed to download the url `%s` after `%s` attempts!",
        url, constants.FETCH_URL_MAX_ATTEMPTS)

    raise Exception(f"Failed to download the url `{url} after {constants.FETCH_URL_MAX_ATTEMPTS} attempts!")



def make_soup_query_and_validate_number(soup, query, number_of_elements_expected):

    result = soup.select(query)

    # if number_of_elements_expected is `-1`, then we it can be 0 to many, so just don't check
    if number_of_elements_expected != -1:
        if len(result) != number_of_elements_expected:

            logger.error("query ( `%s`) did not return the expected number of results: `%s`, but instead returned `%s`",
                query, number_of_elements_expected, len(result))

            raise Exception("query `{}` did not return the expected number of results".format(query))

    return result


def register_ctrl_c_signal_handler(func_to_run):

    def inner_ctrl_c_signal_handler(sig, frame):

        logger.info("SIGINT caught!")
        func_to_run()

    signal.signal(signal.SIGINT, inner_ctrl_c_signal_handler)

class ArrowLoggingFormatter(logging.Formatter):
    ''' logging.Formatter subclass that uses arrow, that formats the timestamp
    to the local timezone (but its in ISO format)
    '''

    def formatTime(self, record, datefmt=None):
        return arrow.get("{}".format(record.created), "X").to("local").isoformat()


def _get_key_or_throw(conf_obj, key, type:HoconTypesEnum):
    '''
    returns the value at the hocon config for the given key, or throws
    an exception

    @param conf_obj the config object (probably the root object)
    @param key - the key we want from the conf_obj
    @param type - a member of HoconTypesEnum of what type we want are expecting
    out of the config
    '''

    try:
        if type == HoconTypesEnum.STRING:
            return conf_obj.get_string(key)
        elif type == HoconTypesEnum.INT:
            return conf_obj.get_int(key)
        elif type == HoconTypesEnum.FLOAT:
            return conf_obj.get_float(key)
        elif type == HoconTypesEnum.LIST:
            return conf_obj.get_list(key)
        elif type == HoconTypesEnum.BOOLEAN:
            return conf_obj.get_bool(key)
        elif type == HoconTypesEnum.CONFIG:
            return conf_obj.get_config(key)
        elif type == HoconTypesEnum.ANY:
            return conf_obj.get(key)
        else:
            raise Exception(f"unknown HoconTypesEnum type `{type}`")
    except Exception as e:
        raise Exception(
            f"Unable to get the key `{key}`, using the type `{type}` from the config because of: `{e}`") from e

def parse_config(stringArg):
    ''' parse the config into our settings object

    '''

    try:
        conf_obj = hocon_config_file_type(stringArg)

        sleep_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_TIME_BETWEEN_REQS_SECS}"
        sleep_time_seconds = _get_key_or_throw(conf_obj, sleep_key, HoconTypesEnum.INT)

        cookies_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_COOKIES_KEY}"
        cookies_dict = _get_key_or_throw(conf_obj, cookies_key, HoconTypesEnum.CONFIG)

        # get cookies
        tmp_cookie_list = []
        for cookie_key, cookie_value in cookies_dict.items():

            cookie = model.CookieKeyValue(key=cookie_key, value=cookie_value)
            tmp_cookie_list.append(cookie)

        cookie_jar = model.CookieJar(cookies=tmp_cookie_list)

        # get headers
        headers_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_HEADERS_KEY}"
        headers_dict = _get_key_or_throw(conf_obj, headers_key, HoconTypesEnum.CONFIG)

        tmp_header_list = []
        for header_key, header_value in headers_dict.items():

            header = model.HeaderKeyValue(key=header_key, value=header_value)
            tmp_header_list.append(header)

        header_jar = model.HeaderJar(headers=tmp_header_list)

        db_config_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_DATABASE_GROUP}"
        sqla_url = get_sqlalchemy_url_from_hocon_config(conf_obj[db_config_key])

        logging_dict_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_LOGGING_DICT_KEY}"
        logging_dict = _get_key_or_throw(conf_obj, logging_dict_key, HoconTypesEnum.CONFIG)

        rabbitmq_url_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_KEY_RABBITMQ_GROUP}"
        rabbitmq_url = _get_rabbitmq_url_from_hocon_config(conf_obj[rabbitmq_url_key])

        rabbitmq_queue_name_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_KEY_RABBITMQ_GROUP}.{constants.HOCON_CONFIG_KEY_RABBITMQ_QUEUE_NAME}"
        rabbitmq_queue_name = _get_key_or_throw(conf_obj, rabbitmq_queue_name_key, HoconTypesEnum.STRING)

        fa_starting_id_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_STARTING_SUBMISSION_ID}"
        fa_starting_id = _get_key_or_throw(conf_obj, fa_starting_id_key, HoconTypesEnum.INT)

        fa_ending_id_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_ENDING_SUBMISSION_ID}"
        fa_ending_id = _get_key_or_throw(conf_obj, fa_ending_id_key, HoconTypesEnum.INT)

        fa_range_step_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_SUBMISSION_ID_RANGE_STEP}"
        fa_range_step = _get_key_or_throw(conf_obj, fa_range_step_key, HoconTypesEnum.INT)

        temp_folder_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_TEMP_FOLDER}"
        temp_folder = pathlib.Path(_get_key_or_throw(conf_obj, temp_folder_key, HoconTypesEnum.STRING))

        wget_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_WGET_PATH}"
        wget = pathlib.Path(_get_key_or_throw(conf_obj, wget_key, HoconTypesEnum.STRING))


        # return final settings
        return model.Settings(
            time_between_requests_seconds=sleep_time_seconds,
            cookie_jar=cookie_jar,
            header_jar=header_jar,
            sqla_url=sqla_url,
            logging_config=logging_dict,
            rabbitmq_url=rabbitmq_url,
            rabbitmq_queue_name=rabbitmq_queue_name,
            starting_submission_id=fa_starting_id,
            ending_submission_id=fa_ending_id,
            submission_id_range_step=fa_range_step,
            temp_folder=temp_folder,
            wget_path=wget,
            cookie_path=temp_folder / constants.COOKIE_FILE_NAME)

    except Exception as e:
        raise argparse.ArgumentTypeError(f"Failed to parse the config: `{e}`")


def hocon_config_file_type(stringArg):
    ''' argparse type method that returns a pyhocon Config object
    or raises an argparse.ArgumentTypeError if this file doesn't exist

    @param stringArg - the argument given to us by argparse
    @return a dict like object containing the configuration or raises ArgumentTypeError
    '''
    resolved_path = pathlib.Path(stringArg).expanduser().resolve()
    if not resolved_path.exists:
        raise argparse.ArgumentTypeError("The path {} doesn't exist!".format(resolved_path))

    conf = None
    try:
        conf = pyhocon.ConfigFactory.parse_file(str(resolved_path))
    except Exception as e:
        raise argparse.ArgumentTypeError(
            "Failed to parse the file `{}` as a HOCON file due to an exception: `{}`".format(resolved_path, e))

    return conf

def isFileType(strict=True):
    def _isFileType(filePath):
        ''' see if the file path given to us by argparse is a file
        @param filePath - the filepath we get from argparse
        @return the filepath as a pathlib.Path() if it is a file, else we raise a ArgumentTypeError'''

        path_maybe = pathlib.Path(filePath)
        path_resolved = None

        # try and resolve the path
        try:
            path_resolved = path_maybe.resolve(strict=strict).expanduser()

        except Exception as e:
            raise argparse.ArgumentTypeError("Failed to parse `{}` as a path: `{}`".format(filePath, e))

        # double check to see if its a file
        if strict:
            if not path_resolved.is_file():
                raise argparse.ArgumentTypeError("The path `{}` is not a file!".format(path_resolved))

        return path_resolved
    return _isFileType

def isDirectoryType(filePath):
    ''' see if the file path given to us by argparse is a directory
    @param filePath - the filepath we get from argparse
    @return the filepath as a pathlib.Path() if it is a directory, else we raise a ArgumentTypeError'''

    path_maybe = pathlib.Path(filePath)
    path_resolved = None

    # try and resolve the path
    try:
        path_resolved = path_maybe.resolve(strict=True).expanduser()

    except Exception as e:
        raise argparse.ArgumentTypeError("Failed to parse `{}` as a path: `{}`".format(filePath, e))

    # double check to see if its a file
    if not path_resolved.is_dir():
        raise argparse.ArgumentTypeError("The path `{}` is not a file!".format(path_resolved))

    return path_resolved


def _get_rabbitmq_url_from_hocon_config(config:pyhocon.ConfigTree) -> yarl.URL:

    scheme = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_RABBITMQ_SCHEME, HoconTypesEnum.STRING)
    user = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_RABBITMQ_USERNAME, HoconTypesEnum.STRING)
    password = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_RABBITMQ_PASSWORD, HoconTypesEnum.STRING)
    host = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_RABBITMQ_HOST, HoconTypesEnum.STRING)
    port = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_RABBITMQ_PORT, HoconTypesEnum.STRING)
    path = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_RABBITMQ_PATH, HoconTypesEnum.STRING)
    query = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_RABBITMQ_QUERY, HoconTypesEnum.CONFIG)

    return yarl.URL.build(
        scheme=scheme,
        user=user,
        password=password,
        host=host,
        port=port,
        path=path,
        query=query,
        encoded=False)

def get_sqlalchemy_url_from_hocon_config(config:pyhocon.ConfigTree) -> URL:

    driver = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_DATABASE_DRIVER, HoconTypesEnum.STRING)
    user = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_DATABASE_USER, HoconTypesEnum.STRING)
    password = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_DATABASE_PASSWORD, HoconTypesEnum.STRING)
    host = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_DATABASE_HOST, HoconTypesEnum.STRING)
    port = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_DATABASE_PORT, HoconTypesEnum.STRING)
    db = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_DATABASE_DATABASE, HoconTypesEnum.STRING)
    query = _get_key_or_throw(config, constants.HOCON_CONFIG_KEY_DATABASE_QUERY, HoconTypesEnum.CONFIG)

    return URL.create(drivername=driver,
        username=user,
        password=password,
        host=host,
        port=port,
        database=db,
        query=query)

def sqlalchemy_pool_on_connect_listener(dbapi_connection, connection_record):
    ''' a sqlalchemy listener method that listens to the 'connect' event on a Pool

    https://docs.sqlalchemy.org/en/13/core/events.html#sqlalchemy.events.PoolEvents.connect

    @param dbapi_connection – a DBAPI connection.

    @param connection_record – the _ConnectionRecord managing the DBAPI connection.

    FIXME: this probably only works if we are sqlite, maybe we should have some code
    to verify if we are sqlite first before we attach this listener?
    '''

    logger.debug("sqlalchemy_pool_on_connect_listener: enabling foreign keys")
    dbapi_connection.execute("PRAGMA foreign_keys = ON")

    fk_result = dbapi_connection.execute("PRAGMA foreign_keys")
    logger.debug("sqlalchemy_pool_on_connect_listener: it is now: `%s`", fk_result.fetchone())

    logger.debug("sqlalchemy_pool_on_connect_listener: setting WAL journaling mode")
    dbapi_connection.execute("PRAGMA journal_mode = WAL")

    wal_result = dbapi_connection.execute("PRAGMA journal_mode")
    logger.debug("sqlalchemy_pool_on_connect_listener: it is now: `%s`", wal_result.fetchone())

def setup_sqlalchemy_engine(sqla_url:URL) -> sqlalchemy.ext.asyncio.AsyncEngine:
    '''
    method to set up the sqlalchemy engine

    this can be overridden in a subclass to configure the engine further

    @return a sqlalchemy.ext.asyncio.AsyncEngine instance
    '''

    # use repr so it doesn't log the password
    logger.info("creating engine using url: `%s`", repr(sqla_url))

    # lets support sqlalchemy 2.0 for future proofing
    # see https://docs.sqlalchemy.org/en/14/changelog/migration_20.html
    result_engine = create_async_engine(sqla_url, echo=False, future=True)

    # attach a listener to the pool
    # see https://docs.sqlalchemy.org/en/13/core/event.html
    # TODO: get rid of maybe? only needed for sqlite
    # listen(result_engine, 'connect', sqlalchemy_pool_on_connect_listener)

    return result_engine

def compress_and_hash_text_data(binary_data:bytes) -> model.CompressAndHashResult:
    '''
    compresses and hashes a string value into a tar.xz (LZMA) file

    @param binary_data - the binary data to compress
    @returns a model.CompressAndHashResult object
    '''

    hasher = hashlib.sha512()

    hasher.update(binary_data)
    original_sha512 = hasher.hexdigest()
    logger.debug("compressing bytes of length `%s` to tar.xz (LZMA), sha512: `%s`", len(binary_data), original_sha512)

    binary_data_fileobj = io.BytesIO()
    binary_data_fileobj.write(binary_data)
    binary_data_fileobj.seek(0)

    tar_fileobj = io.BytesIO()

    with tarfile.open(mode="w:xz", fileobj=tar_fileobj) as tf:

        tarinfo = tarfile.TarInfo(name="webpage_data.txt")
        # have to edit the size and name because its not a real file bleh
        # see https://bugs.python.org/issue22468 and https://bugs.python.org/issue22208 (my bug actually)
        tarinfo.size = len(binary_data_fileobj.getvalue())

        tf.addfile(tarinfo, binary_data_fileobj)

    final_bytes = tar_fileobj.getvalue()

    hasher = hashlib.sha512()
    hasher.update(final_bytes)
    compressed_sha512 = hasher.hexdigest()

    logger.debug("final .tar.xz file is `%s` bytes, sha512: `%s`", len(final_bytes), compressed_sha512)

    result = model.CompressAndHashResult(
        compressed_data=final_bytes,
        original_data_sha512=original_sha512,
        compressed_data_sha512=compressed_sha512)

    return result

class CompressedTimedRotatingFileHandler(TimedRotatingFileHandler):
    ''' class that compressed a file after a certain time period
    when it rolls over

    if the filename contains `{date}`, it will be replaced with the current date

    note: this does NOT handle backupCount, probably because we
    rename the backup files to have a tar.xz suffix and
    the base class doesn't know how to look for those
    '''

    def __init__(self,
        filename,
        when='h',
        interval=1,
        backupCount=0,
        encoding=None,
        delay=False,
        utc=False,
        atTime=None):


        new_filename = filename

        if constants.COMPRESSED_TIMED_ROTATING_FILE_HANDLER_ISO8601_REPLACEMENT in filename:

            date_str = arrow.utcnow().format(constants.ARROW_FILESYSTEM_SAFE_ISO8601_FORMAT)
            filesystem_safe_date_str = date_str.replace(":", "_")
            format_dict = {constants.COMPRESSED_TIMED_ROTATING_FILE_HANDLER_ISO8601_REPLACEMENT: filesystem_safe_date_str}
            new_filename = new_filename.format_map(format_dict)

        p = pathlib.Path(new_filename)

        # create directory if it doesn't exist so that way app code doesn't have
        # to worry about creating a 'log' folder if the config changes
        if not p.parent.exists():
            p.parent.mkdir(parents=True)

        super().__init__(
            new_filename,
            when,
            interval,
            backupCount,
            encoding,
            delay,
            utc,
            atTime)

    def doRollover(self):

        super().doRollover()

        TAR_XZ_SUFFIX = ".tar.xz"

        base_path = pathlib.Path(self.baseFilename)
        parent_folder = base_path.parent

        to_compress_list = []

        # figure out what files haven't been compressed yet
        for iter_child in parent_folder.iterdir():

            # we only care about files, not directories
            if iter_child.is_dir():
                continue

            # don't compress the current file
            if iter_child == base_path:
                continue

            if not iter_child.name.endswith(TAR_XZ_SUFFIX):
                to_compress_list.append(iter_child)

        # now compress the files
        for iter_file in to_compress_list:

            compressed_path = iter_file.with_suffix(iter_file.suffix + TAR_XZ_SUFFIX)

            # add the file to the tar.xz to compress it
            with tarfile.open(compressed_path, mode="w:xz") as t:

                t.add(iter_file, arcname=iter_file.name)

            # delete the file after we compressed it
            iter_file.unlink()

async def run_command_and_wait(
    binary_to_run:pathlib.Path,
    argument_list:list[str],
    timeout:int,
    acceptable_return_codes:list[int],
    cwd=None) -> str:

    logger.debug("running `%s` process with arguments `%s` and cwd `%s`",
        binary_to_run.name,
        argument_list, cwd)

    process_obj:asyncio.subprocess.Process = await asyncio.create_subprocess_exec(
        binary_to_run,
        *argument_list,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        cwd=cwd)

    while True:
        try:
            logger.debug("Waiting for `%s` process to exit...", binary_to_run.name)

            await asyncio.wait_for(
                # wait_for will cancel the task if it times out
                # so wrap the `asyncio.subprocess.Process` object
                # in `shield()` so it doesn't get cancelled
                asyncio.shield(process_obj.wait()),
                timeout=timeout)

            break

        except Exception as e:
            logger.debug("command `%s` timed out, trying again", binary_to_run.name)

    stdout_result = await process_obj.stdout.read()
    stdout_output = stdout_result.decode("utf-8")
    logger.debug("the `%s` process exited: `%s`", binary_to_run.name, process_obj)

    if process_obj.returncode not in acceptable_return_codes:

        logger.error("command `%s` with arguments `%s` 's return code of `%s` wasn't in the list of " +
                "acceptable return codes `%s`, stdout: `%s`",
                binary_to_run, argument_list, process_obj.returncode, acceptable_return_codes, stdout_output)
        raise Exception(f"Command `{binary_to_run}` with arguments `{argument_list}` 's return code " +
            f"`{process_obj.returncode}` was not in the list of acceptable return codes: `{acceptable_return_codes}`")

    return stdout_output


