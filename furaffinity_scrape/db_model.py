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

class SubmissionWebPage(CustomDeclarativeBase):

    __tablename__ = "submission_webpage"

    submission_webpage_id = Column(Integer, nullable=False, autoincrement=True)

    date_visited = Column(ArrowType, nullable=False)

    submission_id = Column(Integer, nullable=False)

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

class SubmissionCounter(CustomDeclarativeBase):
    __tablename__ = "submission_counter"

    submission_counter_id = Column(Integer, nullable=False, autoincrement=True)

    date_visited = Column(ArrowType, nullable=False)

    submission_id = Column(Integer, nullable=False)

    submission_status = Column(ChoiceType(model.SubmissionStatus, impl=Unicode()), nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("submission_counter_id", name="PK-submission_counter-submission_counter_id"),
        Index("IX-submission_counter-date_visited", "date_visited"),
        Index("IX-submission_counter-submission_id", "submission_id"),
        Index("IX-submission_counter-submission_status", "submission_status"),
    )

class FAUsersFound(CustomDeclarativeBase):
    __tablename__ = "fa_users_found"

    # primary key column
    user_id = Column(Integer, nullable=False, autoincrement=True)

    date_added = Column(ArrowType, nullable=False)

    user_name = Column(Unicode, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("user_id", name="PK-fa_users_found-user_id"),

        Index("IX-fa_users_found-date_added", "date_added"),
        Index("IXUQ-fa_users_found-user_name", "user_name", unique=True),

    )


class URLSVisited(CustomDeclarativeBase):
    __tablename__ = "urls_visited"

    # primary key column
    url_visited_id = Column(Integer, nullable=False, autoincrement=True)

    date_added = Column(ArrowType, nullable=False)

    url = Column(URLType, nullable=False)

    status = Column(ChoiceType(model.DatabaseQueueStatusEnum, impl=Unicode()))

    __table_args__ = (
        PrimaryKeyConstraint("url_visited_id", name="PK-urls_visited-user_id"),

        Index("IX-urls_visited-date_added", "date_added"),
        Index("IXUQ-urls_visited-url", "url", unique=True),

    )

class Queue(CustomDeclarativeBase):
    __tablename__ = "queue"

    queue_id = Column(Integer, nullable=False, autoincrement=True)

    url_visited_id = Column(Integer,
        ForeignKey("urls_visited.url_visited_id", name="FK-queue_url_visited_id-urls_visited-url_visited_id"),
        nullable=False)

    url = relationship("URLSVisited")



    __table_args__ = (
        PrimaryKeyConstraint("queue_id", name="PK-queue-queue_id"),
        Index("IX-queue-url_visited_id", "url_visited_id")

    )