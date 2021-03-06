import enum
import re


# colons are invalid characters on windows
# so `arrow.utcnow().isoformat()` returns
# '2021-03-22T00:14:43.819410+00:00', lets replace the colons with
# underscore, and have the timezone be `Z` instead of `ZZ` so
# it outputs as `+0000` instead of `+00:00`
ARROW_FILESYSTEM_SAFE_ISO8601_FORMAT = "YYYY-MM-DDTHH_mm_ss.SSSSSSZ"

# specify this in the filename of the CompressedTimedRotatingFileHandler class to have
# the timestamp inserted into the filename (filesystem safe version of it)
COMPRESSED_TIMED_ROTATING_FILE_HANDLER_ISO8601_REPLACEMENT = "iso8601_timestamp"

RELATIVE_URL_RE_KEY = "username"
# from their registration page:
# "Only letters and numbers, dash, underscore, tilde and a period are allowed."
# except just kidding, the characters `]` and `[` also work, even though it says they don't
# when you create a new account, but this profile exists: https://www.furaffinity.net/user/]-[3l/
# haha found another one, carets are apparently allowed: https://www.furaffinity.net/user/^nobodysville^/
FA_USERNAME_ALLOWED_CHARS = "a-zA-Z0-9_\-~.`\[\]^"
RELATIVE_URL_RE = re.compile(f"^/user/(?P<{RELATIVE_URL_RE_KEY}>[{FA_USERNAME_ALLOWED_CHARS}]+)/?$")
FURAFFINITY_USERNAME_RE = re.compile(f"^https?://(www.)?furaffinity.net/user/(?P<{RELATIVE_URL_RE_KEY}>[{FA_USERNAME_ALLOWED_CHARS}]+)/?$")
FURAFFINITY_RELATIVE_USERNAME_RE = re.compile(f"^/user/(?P<{RELATIVE_URL_RE_KEY}>[{FA_USERNAME_ALLOWED_CHARS}]+)/?$")

HOCON_CONFIG_TOP_LEVEL_KEY = "furaffinity_scrape"
HOCON_CONFIG_COOKIES_KEY = "cookies"
HOCON_CONFIG_HEADERS_KEY = "headers"
HOCON_CONFIG_TIME_BETWEEN_REQS_SECS = "time_between_requests_seconds"
HOCON_CONFIG_LOGGING_DICT_KEY = "logging_dict"
HOCON_CONFIG_STARTING_SUBMISSION_ID = "starting_submission_id"
HOCON_CONFIG_ENDING_SUBMISSION_ID = "ending_submission_id"

HOCON_CONFIG_DATABASE_GROUP = "database"
HOCON_CONFIG_KEY_DATABASE_DRIVER = "driver_name"
HOCON_CONFIG_KEY_DATABASE_USER = "user_name"
HOCON_CONFIG_KEY_DATABASE_PASSWORD = "password"
HOCON_CONFIG_KEY_DATABASE_HOST = "host"
HOCON_CONFIG_KEY_DATABASE_PORT = "port"
HOCON_CONFIG_KEY_DATABASE_DATABASE = "database"
HOCON_CONFIG_KEY_DATABASE_QUERY = "query"

HOCON_CONFIG_KEY_RABBITMQ_GROUP = "rabbitmq"
HOCON_CONFIG_KEY_RABBITMQ_SCHEME = "scheme"
HOCON_CONFIG_KEY_RABBITMQ_USERNAME = "username"
HOCON_CONFIG_KEY_RABBITMQ_PASSWORD = "password"
HOCON_CONFIG_KEY_RABBITMQ_HOST = "host"
HOCON_CONFIG_KEY_RABBITMQ_PORT = "port"
HOCON_CONFIG_KEY_RABBITMQ_PATH = "path"
HOCON_CONFIG_KEY_RABBITMQ_QUERY = "query"

HOCON_CONFIG_KEY_RABBITMQ_QUEUE_NAME = "queue_name"

RABBITMQ_JSON_SUBMISSION_ID_KEY = "submission_id"


FETCH_URL_MAX_ATTEMPTS = 5
FETCH_URL_TIME_TO_SLEEP_BETWEEN_ATTEMPTS_SECONDS = 5

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
