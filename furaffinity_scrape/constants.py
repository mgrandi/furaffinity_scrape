import enum
import re

RELATIVE_URL_RE_KEY = "username"
# from their registration page:
# "Only letters and numbers, dash, underscore, tilde and a period are allowed."
FA_USERNAME_ALLOWED_CHARS = "a-zA-Z0-9_\-~.`"
RELATIVE_URL_RE = re.compile(f"^/user/(?P<{RELATIVE_URL_RE_KEY}>[{FA_USERNAME_ALLOWED_CHARS}]+)/?$")
FURAFFINITY_USERNAME_RE = re.compile(f"^https?://(www.)?furaffinity.net/user/(?P<{RELATIVE_URL_RE_KEY}>[{FA_USERNAME_ALLOWED_CHARS}]+)/?$")
FURAFFINITY_RELATIVE_USERNAME_RE = re.compile(f"^/user/(?P<{RELATIVE_URL_RE_KEY}>[{FA_USERNAME_ALLOWED_CHARS}]+)/?$")

HOCON_CONFIG_TOP_LEVEL_KEY = "furaffinity_scrape"
HOCON_CONFIG_COOKIES_KEY = "cookies"
HOCON_CONFIG_HEADERS_KEY = "headers"
HOCON_CONFIG_TIME_BETWEEN_REQS_SECS = "time_between_requests_seconds"

HOCON_CONFIG_DATABASE_GROUP = "database"
HOCON_CONFIG_KEY_DATABASE_DRIVER = "driver_name"
HOCON_CONFIG_KEY_DATABASE_USER = "user_name"
HOCON_CONFIG_KEY_DATABASE_PASSWORD = "password"
HOCON_CONFIG_KEY_DATABASE_HOST = "host"
HOCON_CONFIG_KEY_DATABASE_PORT = "port"
HOCON_CONFIG_KEY_DATABASE_DATABASE = "database"
HOCON_CONFIG_KEY_DATABASE_QUERY = "query"

HTTPBIN_URL = "https://httpbin.org/anything"

FURAFFINITY_URL_SUBMISSION = "https://www.furaffinity.net/view/{}/"

SUBMISSION_DOESNT_EXIST_TEXT = "The submission you are trying to find is not in our database.                \nClick here to go back"

class HoconTypesEnum(enum.Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    LIST = "list"
    BOOLEAN = "boolean"
    CONFIG = "config"
    ANY = "any"
