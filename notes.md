# random notes

## patching sqlalchemy_utils

it seems that using the beta version of sqlalchemy means some of the library
imports have changed, this is what i changed in the `sqlalchemy_utils` library:

`sqlalchemy_utils\functions\orm.py`

i had to change

`from sqlalchemy.orm.query import _ColumnEntity`

to

`from sqlalchemy.orm.context import _ColumnEntity`

i guess the class was moved in sqlalchemy version `1.4.0b3`


TODO:

maybe switch to yarl instead of furl?