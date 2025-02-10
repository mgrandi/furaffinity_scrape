import asyncio
import logging

import aio_pika
import arrow
from sqlalchemy import select, desc, text, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert
from thespian.initmsgs import initializing_messages
import attr
import thespian
import thespian.actors

from furaffinity_scrape import utils
from furaffinity_scrape import db_model
from furaffinity_scrape import model
from furaffinity_scrape.actors.common_actor_messages import PleaseStop

logger = logging.getLogger(__name__)


@attr.s(auto_attribs=True, frozen=True, kw_only=True)
class QueueLatestSubmissionsRootActorProps:

    settings:model.Settings = attr.ib()


@initializing_messages(
    [("actor_settings", QueueLatestSubmissionsRootActorProps, False)], initdone="init_completed", init_passthru=False)
class QueueLatestSubmissionsRootActor(thespian.actors.Actor):

    # we don't have props here so use the initalization messages pattern
    # https://thespianpy.com/doc/using#outline-container-hH-d4e592db-8bab-45bd-9643-e952510bd7dc


    def init_completed(self):

        self.config = self.actor_settings.settings


        logger.info("init completed")
        #self.rabbit_actor = self.createActor()

    def receiveMessage(self, message, sender):

        match type(message):

            case thespian.actors.ActorExitRequest:
                logger.info("Asked to exit")



