import enum

HOCON_CONFIG_TOP_LEVEL_KEY = "furaffinity_scrape"
HOCON_CONFIG_COOKIES_KEY = "cookies"

class HoconTypesEnum(enum.Enum):
    STRING = "string"
    INT = "int"
    FLOAT = "float"
    LIST = "list"
    BOOLEAN = "boolean"
    CONFIG = "config"
    ANY = "any"
