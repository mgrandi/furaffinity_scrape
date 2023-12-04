import logging

from furaffinity_scrape import model

from sqlalchemy import Column, Index, Integer, Unicode, LargeBinary, ForeignKey, UniqueConstraint, PrimaryKeyConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy_repr import RepresentableBase
from sqlalchemy_utils.types.url import URLType
from sqlalchemy_utils.types.arrow import ArrowType
from sqlalchemy_utils.types.choice import ChoiceType

logger = logging.getLogger(__name__)

CustomDeclarativeBase = declarative_base(cls=RepresentableBase, name="CustomDeclarativeBase")

class SubmissionWebpage(CustomDeclarativeBase):

    __tablename__ = "submission_webpage"

    submission_webpage_id = Column(Integer, nullable=False, autoincrement=True)

    submission_id = Column(Integer,
        ForeignKey("submission.submission_id",
            name="FK-submission_webpage-submission_id-submission-submission_id"),
        nullable=False)

    submission = relationship("Submission")

    date_visited = Column(ArrowType, nullable=False)

    raw_compressed_webpage_data = Column(LargeBinary, nullable=False)

    encoding_status = Column(ChoiceType(model.EncodingStatusEnum, impl=Unicode()), nullable=False)

    original_data_sha512 = Column(Unicode, nullable=False)

    compressed_data_sha512 = Column(Unicode, nullable=False)


    __table_args__ = (
        PrimaryKeyConstraint("submission_webpage_id", name="PK-submission_webpage-submission_webpage_id"),
        Index("IX-submission_webpage-date_visited", "date_visited"),
        Index("IX-submission_webpage-submission_id", "submission_id"),
        Index("IX-submission_webpage-original_data_sha512", "original_data_sha512"),
        Index("IX-submission_webpage-compressed_data_sha512", "compressed_data_sha512"),

    )

class Submission(CustomDeclarativeBase):
    __tablename__ = "submission"

    submission_id = Column(Integer, nullable=False, autoincrement=True)

    furaffinity_submission_id = Column(Integer, nullable=False)

    date_visited = Column(ArrowType, nullable=False)

    submission_status = Column(ChoiceType(model.SubmissionStatus, impl=Unicode()), nullable=False)

    processed_status = Column(ChoiceType(model.ProcessedStatus, impl=Unicode()), nullable=False)

    claimed_by = Column(Unicode, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("submission_id", name="PK-submission-submission_id"),
        Index("IX-submission-furaffinity_submission_id", "furaffinity_submission_id"),
        Index("IX-submission-date_visited", "date_visited"),
        Index("IX-submission-submission_status", "submission_status"),
        Index("IX-submission-processed_status", "processed_status"),
        Index("IX-submission-claimed_by", "claimed_by"),
    )

class User(CustomDeclarativeBase):
    __tablename__ = "user"

    # primary key column
    user_id = Column(Integer, nullable=False, autoincrement=True)

    date_added = Column(ArrowType, nullable=False)

    user_name = Column(Unicode, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("user_id", name="PK-user-user_id"),
        Index("IX-user-date_added", "date_added"),
        Index("IXUQ-user-user_name", "user_name", unique=True),
    )


class FAScrapeAttempt(CustomDeclarativeBase):

    __tablename__ = "fa_scrape_attempt"

    scrape_attempt_id = Column(Integer, nullable=False, autoincrement=True)

    furaffinity_submission_id = Column(Integer, nullable=False)

    date_visited = Column(ArrowType, nullable=False)

    processed_status = Column(ChoiceType(model.ProcessedStatus, impl=Unicode()), nullable=False)

    claimed_by = Column(Unicode, nullable=False)

    error_string = Column(Unicode, nullable=True)

    __table_args__ = (
        PrimaryKeyConstraint("scrape_attempt_id", name="PK-fa_scrape_attempt-scrape_attempt_id"),
        Index("IX-fa_scrape_attempt-furaffinity_submission_id", "furaffinity_submission_id"),
        Index("IX-fa_scrape_attempt-furaffinity_submission_id-processed_status", "furaffinity_submission_id", "processed_status"),
    )


class FAScrapeContent(CustomDeclarativeBase):
    __tablename__ = "fa_scrape_content"

    content_id = Column(Integer, nullable=False, autoincrement=True)

    attempt_id = Column(Integer,
        ForeignKey("fa_scrape_attempt.scrape_attempt_id",
            name="FK-fa_scrape_content-a_id-fa_scrape_attempt-scrape_attempt_id"),
        nullable=False)

    content_length = Column(Integer, nullable=False)
    content_sha512 = Column(Unicode, nullable=False)
    content_binary = Column(LargeBinary, nullable=True)

    attempt = relationship("FAScrapeAttempt")
    # for sqlalchemy_repr, don't log the content_binary column
    # see https://github.com/manicmaniac/sqlalchemy-repr/blob/master/sqlalchemy_repr.py
    # needs to be A LIST, if you do set("lol") then it will be a set of {"l", "o"}, not the string value
    # not sure if i need to do this for `relationship` columns but lets be safe
    __repr_blacklist__ = ["content_binary"]

    __table_args__ = (
        PrimaryKeyConstraint("content_id", name="PK-fa_scrape_content-content_id"),
        Index("IX-fa_scrape_content-attempt_id", "attempt_id"),


    )


# class URLSVisited(CustomDeclarativeBase):
#     __tablename__ = "urls_visited"
#     # primary key column
#     url_visited_id = Column(Integer, nullable=False, autoincrement=True)
#     date_added = Column(ArrowType, nullable=False)
#     url = Column(URLType, nullable=False)
#     status = Column(ChoiceType(model.DatabaseQueueStatusEnum, impl=Unicode()))
#     __table_args__ = (
#         PrimaryKeyConstraint("url_visited_id", name="PK-urls_visited-user_id"),
#         Index("IX-urls_visited-date_added", "date_added"),
#         Index("IXUQ-urls_visited-url", "url", unique=True),
#     )

# class Queue(CustomDeclarativeBase):
#     __tablename__ = "queue"
#     queue_id = Column(Integer, nullable=False, autoincrement=True)
#     url_visited_id = Column(Integer,
#         ForeignKey("urls_visited.url_visited_id", name="FK-queue-url_visited_id-urls_visited-url_visited_id"),
#         nullable=False)
#     url = relationship("URLSVisited")
#     __table_args__ = (
#         PrimaryKeyConstraint("queue_id", name="PK-queue-queue_id"),
#         Index("IX-queue-url_visited_id", "url_visited_id")
#     )