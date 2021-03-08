# furaffinity_scrape

NOTE: i have to patch sqlalchemy_utils:

`sqlalchemy_utils\functions\orm.py`

i had to change

`from sqlalchemy.orm.query import _ColumnEntity`

to

`from sqlalchemy.orm.context import _ColumnEntity`

i guess the class was moved in sqlalchemy version `1.4.0b3`


TODO:

maybe switch to yarl instead of furl?