import pathlib
import logging
import pyhocon

import arrow
import sqlalchemy
from sqlalchemy.engine import Engine
from sqlalchemy.engine.url import URL
from sqlalchemy import create_engine
from sqlalchemy.event import listen


from furaffinity_scrape import constants
from furaffinity_scrape.constants import HoconTypesEnum

from furaffinity_scrape import model

logger = logging.getLogger(__name__)

class ArrowLoggingFormatter(logging.Formatter):
    ''' logging.Formatter subclass that uses arrow, that formats the timestamp
    to the local timezone (but its in ISO format)
    '''

    def formatTime(self, record, datefmt=None):
        return arrow.get("{}".format(record.created), "X").to("local").isoformat()

def parse_config(stringArg):
    ''' parse the config into our settings object

    '''

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




    conf_obj = hocon_config_file_type(stringArg)

    cookies_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_COOKIES_KEY}"
    cookies_dict = _get_key_or_throw(conf_obj, cookies_key, HoconTypesEnum.CONFIG)

    # get cookies
    tmp_cookie_list = []
    for cookie_key, cookie_value in cookies_dict.items():

        cookie = model.CookieKeyValue(key=cookie_key, value=cookie_value)
        tmp_cookie_list.append(cookie)

    cookie_jar = model.CookieJar(cookies=tmp_cookie_list)

    db_config_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_DATABASE_GROUP}"
    sqla_url = get_sqlalchemy_url_from_hocon_config(conf_obj[db_config_key])

    # return final settings
    return model.Settings(cookie_jar=cookie_jar, sqla_url=sqla_url)




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


def get_sqlalchemy_url_from_hocon_config(config:pyhocon.ConfigTree) -> URL:

    driver = config.get_string(constants.HOCON_CONFIG_KEY_DATABASE_DRIVER)
    user = config.get_string(constants.HOCON_CONFIG_KEY_DATABASE_USER)
    password = config.get_string(constants.HOCON_CONFIG_KEY_DATABASE_PASSWORD)
    host = config.get_string(constants.HOCON_CONFIG_KEY_DATABASE_HOST)
    port = config.get_string(constants.HOCON_CONFIG_KEY_DATABASE_PORT)
    db = config.get_string(constants.HOCON_CONFIG_KEY_DATABASE_DATABASE)
    query = config.get_string(constants.HOCON_CONFIG_KEY_DATABASE_QUERY)


    return URL(drivername=driver,
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

def setup_sqlalchemy_engine(sqla_url:URL) -> sqlalchemy.engine.Engine:
    '''
    method to set up the sqlalchemy engine

    this can be overridden in a subclass to configure the engine further

    @return a sqlalchemy.engine.Engine instance
    '''

    logger.info("creating engine")

    result_engine = create_engine(sqla_url, echo=False)

    # attach a listener to the pool
    # see https://docs.sqlalchemy.org/en/13/core/event.html
    listen(result_engine, 'connect', sqlalchemy_pool_on_connect_listener)

    return result_engine
