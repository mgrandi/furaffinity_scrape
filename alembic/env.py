import asyncio
import logging
from logging.config import fileConfig
import pathlib

import sqlalchemy
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import create_async_engine

from alembic import context

# this is the Alembic Config object, which provides
# access to the values within the .ini file in use.
config = context.config

# Interpret the config file for Python logging.
# This line sets up loggers basically.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# In previous usages of Alembic, i had to do some `sys.path` manipulation to make it
# so I could import my models, but now this can be done automatically by using alembic.ini
# with the `prepend_sys_path` option.
from furaffinity_scrape import db_model, utils, constants

# add your model's MetaData object here
# for 'autogenerate' support
# from myapp import mymodel
# target_metadata = mymodel.Base.metadata
target_metadata = db_model.CustomDeclarativeBase.metadata

# create a logger for the custom code I wrote in this file
logger = logging.getLogger(__name__)
logger.setLevel("INFO")

# other values from the config, defined by the needs of env.py,
# can be acquired:
# my_important_option = config.get_main_option("my_important_option")
# ... etc.

def get_our_own_sqla_url():
    '''
    Load our own application config and use it to get the SQLAlchemy URL
    '''

    x_arguments  = context.get_x_argument(as_dictionary=True)

    if constants.ALEMBIC_CMD_X_ARGUMENT_NAME not in x_arguments.keys():
        raise Exception("you need to pass in `-x {}=/path/to/config``".format(constants.ALEMBIC_CMD_X_ARGUMENT_NAME))

    our_config_path:str = x_arguments[constants.ALEMBIC_CMD_X_ARGUMENT_NAME]

    logger.info("config file path: `%s`", our_config_path)
    our_config:pathlib.Path = utils.hocon_config_file_type(our_config_path)
    db_config_key = f"{constants.HOCON_CONFIG_TOP_LEVEL_KEY}.{constants.HOCON_CONFIG_DATABASE_GROUP}"
    sqla_url = utils.get_sqlalchemy_url_from_hocon_config(our_config.get_config(db_config_key))

    logger.info("SQLAlchemy URL: `%s`", sqla_url)
    return sqla_url

async def run_async_migrations_with_new_engine():
    """In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    url = get_our_own_sqla_url()

    # connectable = engine_from_config(
    #     config.get_section(config.config_ini_section, {}),
    #     prefix="sqlalchemy.",
    #     poolclass=pool.NullPool,
    # )

    # we get the url from our own config, no need to use engine_from_config

    # see if the driver is async, if it is, then replace it with a non async one
    connectable = create_async_engine(url, poolclass=pool.NullPool)

    async with connectable.connect() as connection:

        await connection.run_sync(run_async_migrations_with_existing_engine)

    await connectable.dispose()

def run_async_migrations_with_existing_engine(connection:sqlalchemy.ext.asyncio.AsyncEngine):
    '''
    now that we are using asyncio to run the migrations, this is the function
    that gets called by run_async_migrations, in a non asyncio way with
    AsyncEngine.run_sync()
    '''

    # use render_as_batch for sqlite
    # https://alembic.sqlalchemy.org/en/latest/batch.html
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        render_as_batch=True
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode.

    This configures the context with just a URL
    and not an Engine, though an Engine is acceptable
    here as well.  By skipping the Engine creation
    we don't even need a DBAPI to be available.

    Calls to context.execute() here emit the given string to the
    script output.

    """
    # url = config.get_main_option("sqlalchemy.url")

    # we get the url from our own config
    url = get_our_own_sqla_url()

    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    """Run migrations in 'online' mode.

    In this scenario we need to create an Engine
    and associate a connection with the context.

    """

    # we now expect a async driver and run the migrations as async
    # see: https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic

    # also, we are calling alembic from inside the application sometimes. If this is true, then
    # we already have a connection, so check to see if its stored in the config attributes
    # dict. If it is set, then use it and call do_run_migrations immediately
    # if not, then call create_engine_andrun_async_migrations() which create the engine
    # and then run any commands
    # see https://alembic.sqlalchemy.org/en/latest/cookbook.html#programmatic-api-use-connection-sharing-with-asyncio
    # and https://alembic.sqlalchemy.org/en/latest/cookbook.html#connection-sharing
    connectable = config.attributes.get("connection", None)

    if connectable is None:
        # no existing connection, might be running in the command line, create the engine
        # and run the migrations
        logger.info("Connectable is None, creating new engine")
        asyncio.run(run_async_migrations_with_new_engine())
    else:
        # we already have a connection, might be running programmatically
        # so just run the migrations
        logger.info("Connectable already exists, reusing")
        run_async_migrations_with_existing_engine(connectable)


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
