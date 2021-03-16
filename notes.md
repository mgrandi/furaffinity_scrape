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

## broken autourl

https://www.furaffinity.net/view/30414

see https://www.furaffinity.net/help#uploads-and-submissions , you can auto add a url for a user
by doing `:iconUSERNAME:` or `@username`, but in the above submission, they just do `__@`, probably as part of an emote,
as in `@__@`, so it made `__` as a username which doesn't work lol, and the html is just this:

```html
<a href="/user/" class="linkusername">__</a>
```

so I had to make it so we just warn on regex mismatches rather than throwing an exception, grumble