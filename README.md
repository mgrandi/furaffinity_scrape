# furaffinity_scrape

Scripts to assist with the scraping of furaffinity.net

They are split into modules

## main usage

```plaintext

> python cli.py --help

usage: cli.py [-h] --config CONFIG {scrape_users} ...

utilities for scraping furaffinity.net

positional arguments:
  {scrape_users}

optional arguments:
  -h, --help       show this help message and exit
  --config CONFIG  the HOCON config file

```


## scrape_users subcommand

a subcommand to build up a database of users by downloading every furaffinity submission in order, parse it with `lxml`
/ `beautifulsoup4`, and then pick out the parts that could be usernames:

* artist
* art descriptions, often link to other users
* usernames of users who comment

this will download a submission:

1: checks to see if the submission has been deleted or not

1.1: if the submission still exists

1.1.1: creates a `beautifulsoup4` object out of the downloaded html

1.1.2: runs CSS selector queries on it to parse out any available usernames

1.2.3: see if the extracted users exist in the database, if not, add them

1.2.4: add submission HTML to the database

2: add row to the database marking that we have processed this submission

Eventually, we will have a sizeable list of users, after which we can iterate over them to download their user pages
to get even more users, through user page comments, watch lists, profile information.