from __future__ import annotations
import typing
import enum

import bs4
from sqlalchemy.engine.url import URL
import attr
import yarl


@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class Settings:

    time_between_requests_seconds:int = attr.ib()
    cookie_jar:CookieJar = attr.ib()
    header_jar:HeaderJar = attr.ib()
    sqla_url:URL = attr.ib()
    logging_config:dict = attr.ib()
    rabbitmq_url:yarl.URL = attr.ib()
    rabbitmq_queue_name:str = attr.ib()
    starting_submission_id:int = attr.ib()
    ending_submission_id:int = attr.ib()

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
class HeaderKeyValue:
    key:str = attr.ib()
    value:str = attr.ib()

@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class HeaderJar:
    headers:typing.Sequence[HeaderKeyValue] = attr.ib()

    def as_aiohttp_header_dict(self):

        result_dict = dict()

        for iter_header_kv in self.headers:
            result_dict[iter_header_kv.key] = iter_header_kv.value

        return result_dict

@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class FASubmission:

    submission_row:typing.Optional[db_model.Submission] = attr.ib()
    raw_html_bytes:typing.Optional[bytes] = attr.ib(repr=False)
    soup:typing.Optional[bs4.BeautifulSoup] = attr.ib(repr=False)
    did_have_decode_error:typing.Optional[bool] = attr.ib()

@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class CompressAndHashResult:

    compressed_data:bytes = attr.ib(repr=False)
    original_data_sha512:str = attr.ib()
    compressed_data_sha512:str = attr.ib()


@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class HtmlQuery:
    description:str = attr.ib()
    func:function = attr.ib()

@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class AiohttpResponseResult:
    '''
    what we return from utils.fetch_url that represents
    a result from aiohttp, including the decoded text,
    raw binary data, and whether or not we had a decoding error
    when decoding the data as utf8
    '''

    decoded_text:str = attr.ib()
    binary_data:bytes = attr.ib()
    encountered_decoding_error:bool = attr.ib()

@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class RabbitmqMessageInfo:

    delivery_tag:int = attr.ib()
    body_bytes:bytes=attr.ib()

class SubmissionStatus(enum.Enum):
    UNKNOWN = "unknown"
    EXISTS = "exists"
    DELETED = "deleted"
    GDPR_DELETED = "gdpr_deleted"

class ProcessedStatus(enum.Enum):
    TODO = "todo"
    FINISHED = "finished"

class EncodingStatusEnum(enum.Enum):
    DECODED_OK = "decoded_ok"
    UNICODE_DECODE_ERROR = "unicode_decode_error"

