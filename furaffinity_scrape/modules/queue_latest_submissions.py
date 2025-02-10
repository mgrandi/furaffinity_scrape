import logging
import json
import asyncio
import pathlib
import argparse

import aio_pika

import arrow
from sqlalchemy import select, desc, text, func
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.postgresql import insert

from furaffinity_scrape import utils
from furaffinity_scrape import db_model
from furaffinity_scrape import model
from furaffinity_scrape.actors.queue_latest_submissions_root_actor \
    import QueueLatestSubmissionsRootActor,QueueLatestSubmissionsRootActorProps
from furaffinity_scrape.actors.common_actor_messages import PleaseStop
import thespian
import thespian.actors

logger = logging.getLogger(__name__)

class QueueLatestSubmissions:



    @staticmethod
    def create_subparser_command(argparse_subparser):
        '''
        populate the argparse arguments for this module

        @param argparse_subparser - the object returned by ArgumentParser.add_subparsers()
        that we call add_parser() on to add arguments and such

        '''

        parser = argparse_subparser.add_parser("queue_latest_submissions")

        queue_latest_submissions_obj = QueueLatestSubmissions()

        # set the function that is called when this command is used
        parser.set_defaults(func_to_run=queue_latest_submissions_obj.run)


    def __init__(self):

        self.config:model.Settings = None
        self.actor_system:thespian.actors.ActorSystem = None
        self.stop_event:asyncio.Event = None
        self.root_actor = None

    async def run(self, parsed_args:argparse.Namespace, stop_event:asyncio.Event):
        '''
        main method
        '''

        logger.debug("running")
        self.config = parsed_args.config
        self.stop_event = stop_event
        self.actor_system = parsed_args.actor_system


        logger.info("Creating root actor")

        self.root_actor = self.actor_system.createActor(QueueLatestSubmissionsRootActor, globalName="RootActor")
        self.actor_system.tell(self.root_actor, QueueLatestSubmissionsRootActorProps(settings=self.config))

        # wait for exit

        logger.info("Waiting for stop event: %s", stop_event)
        await stop_event.wait()



        logger.info("Stop event signaled")

        # send actor stop
        self.actor_system.tell(self.root_actor, thespian.actors.ActorExitRequest())