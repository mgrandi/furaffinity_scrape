import pathlib
import logging
import pyhocon

import arrow

from furaffinity_scrape import constants
from furaffinity_scrape.constants import HoconTypesEnum

from furaffinity_scrape import model


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

    # return final settings
    return model.Settings(cookie_jar=cookie_jar)




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