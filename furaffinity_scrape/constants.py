import enum

HOCON_CONFIG_TOP_LEVEL_KEY = "furaffinity_scrape"
HOCON_CONFIG_COOKIES_KEY = "cookies"

HOCON_CONFIG_DATABASE_GROUP = "database"
HOCON_CONFIG_KEY_DATABASE_DRIVER = "driver_name"
HOCON_CONFIG_KEY_DATABASE_USER = "user_name"
HOCON_CONFIG_KEY_DATABASE_PASSWORD = "password"
HOCON_CONFIG_KEY_DATABASE_HOST = "host"
HOCON_CONFIG_KEY_DATABASE_PORT = "port"
HOCON_CONFIG_KEY_DATABASE_DATABASE = "database"
HOCON_CONFIG_KEY_DATABASE_QUERY = "query"


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
