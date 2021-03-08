from __future__ import annotations
import typing
import enum

import bs4
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

    def as_aiohttp_cookie_dict(self):

        result_dict = dict()

        for iter_cookie_kv in self.cookies:
            result_dict[iter_cookie_kv.key] = iter_cookie_kv.value

        return result_dict

@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class FASubmission:

    submission_id:int = attr.ib()
    soup:typing.Optional[bs4.BeautifulSoup] = attr.ib(repr=False)
    does_exist:typing.Optional[bool] = attr.ib()

@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class HtmlQuery:
    description:str = attr.ib()
    func:function = attr.ib()

class SubmissionStatus(enum.Enum):
    EXISTS = "exists"
    DELETED = "deleted"

class DatabaseQueueStatusEnum(enum.Enum):
    TODO = "todo"
    FINISHED = "finished"