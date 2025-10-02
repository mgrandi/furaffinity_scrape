# Alembic

## upgrading to the latest version

```plaintext
alembic -x furaffinity_scrape_config=YOUR_CONFIGURATION_FILE_HERE.hocon upgrade head
```

## why do you need `-x`

Note you need that `-x furaffinity_scrape_config=YOUR_CONFIGURATION_FILE_HERE.hocon` argument so that `env.py` knows how to connect to the database to do the table comparisons when autogenerating.

## adding a new alembic version

make sure you have run `poetry shell` in the root folder

edit `db_model.py` with your new database object that extends from `CustomDeclarativeBase`

If running on an empty database, make sure you have upgraded to the latest version, or else it will say everything changed and not just your new table.

```plaintext
alembic -x furaffinity_scrape_config=YOUR_CONFIGURATION_FILE_HERE.hocon upgrade head
```

run the alembic autogenerate command

```plaintext

alembic -x furaffinity_scrape_config=YOUR_CONFIGURATION_FILE_HERE.hocon revision --autogenerate -m "add my cool table"

```

this should drop a new file in the `alembic/versions` folder.

Be sure to edit the file to spot check the auto generated schema, for example, custom sqlalchemy column types will have the type but not any arguments. (such as `ChoiceType()`, need to fill that in as `ChoiceType(SomeEnumHere)`). Also double check imports are available for these custom `Column` types, as well as any objects from your own code that you are using.

Now that you have the schema generated, you can run the alembic upgrade command to either upgrade the database or create the tables on an empty database. Be sure to run backups before any upgrades!

```plaintext

alembic -x furaffinity_scrape_config=YOUR_CONFIGURATION_FILE_HERE.hocon upgrade head
INFO  [env_py] Connectable is None, creating new engine
INFO  [env_py] config file path: `YOUR_CONFIGURATION_FILE_HERE.hocon`
INFO  [env_py] SQLAlchemy URL: `REDACTED`
INFO  [alembic.runtime.migration] Context impl PostgresqlImpl.
INFO  [alembic.runtime.migration] Will assume transactional DDL.
INFO  [alembic.runtime.migration] Running upgrade 164a725fdfc7 -> f904059dfcee, add FuraffinityHoleStatus table

```
