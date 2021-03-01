from __future__ import annotations
import typing
import enum

from sqlalchemy.engine.url import URL
import attr


@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class Settings:

    cookie_jar:CookieJar = attr.ib()
    sqla_url:URL = attr.ib()

@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class CookieKeyValue:
    key:str = attr.ib()
    value:str = attr.ib()

@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class CookieJar:
    cookies:typing.Sequence[CookieKeyValue] = attr.ib()



class DatabaseQueueStatusEnum(enum.Enum):
    TODO = "todo"
    FINISHED = "finished"