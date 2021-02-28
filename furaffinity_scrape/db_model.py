import logging

from sqlalchemy import Column, Index, Integer, Unicode,
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy_repr import RepresentableBase
from sqlalchemy_utils.types.url import URLType
from sqlalchemy_utils.types.arrow import ArrowType

logger = logging.getLogger(__name__)

CustomDeclarativeBase = declarative_base(cls=RepresentableBase, name="CustomDeclarativeBase")

class FAUsersFound(CustomDeclarativeBase):
    __tablename__ = "fa_users_found"

    # primary key column
    user_id = Column(Integer, nullable=False)

    date_added = Column(ArrowType, nullable=False)

    user_name = Column(Unicode, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("user_id", name="PK-fa_users_found-user_id"),

        Index("IX-fa_users_found-date_added", "date_added")
        Index("IXUQ-fa_users_found-user_name", "user_name", unique=True),

    )


class URLSVisited(CustomDeclarativeBase):
    __tablename__ = "urls_visited"

    # primary key column
    url_visited_id = Column(Integer, nullable=False)

    date_added = Column(ArrowType, nullable=False)

    url = Column(URLType, nullable=False)

    __table_args__ = (
        PrimaryKeyConstraint("url_visited_id", name="PK-urls_visited-user_id"),

        Index("IX-urls_visited-date_added", "date_added")
        Index("IXUQ-urls_visited-url", "url", unique=True),

    )