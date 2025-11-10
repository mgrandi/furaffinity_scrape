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


## running

### powershell

```plaintext
python cli.py --verbose --no-stdout --log-to-file "C:\Users\mark\Temp\furaffinity_scrape_temporary_folder\logs\$([int][double]::Parse((Get-Date -UFormat %s)))_furaffinity_scrape_output.log" --config "C:\Users\mark\Temp\furaffinity_scrape_temporary_folder\furaffinity_scrape_config.hocon" scrape_users

```

### linux

```plaintext
python cli.py --verbose --no-stdout --log-to-file "/home/mgrandi/faurls/$(date --utc '+%FT%H_%M_%S.%N%z')_furaffinity_scrape.log" --config ../fascraper_config.hocon scrape_users
```

## warcinfo record

```plaintext
software: Wget/1.20.3-at.20211001.01 (linux-gnu)
format: WARC File Format 1.1
conformsTo: http://bibnum.bnf.fr/WARC/WARC_ISO_28500_version1-1_latestdraft.pdf
robots: off
wget-arguments: "/home/mgrandi/faurls/wget" "--no-verbose" "--load-cookies=/home/mgrandi/faurls/temp/cookies.txt" "-e" "robots=off" "--user-agent" "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:129.0) Gecko/20100101 Firefox/129.0 Archivistbird (markgrandi@gmail.com)" "--span-hosts" "--page-requisites" "--no-check-certificate" "--no-warc-compression" "--tries" "5" "--waitretry" "5" "--warc-tempdir" "/home/mgrandi/faurls/temp/fa_item_217022_mk1wn889/warc_temp_folder" "--warc-header" "operator: Mark Grandi (markgrandi@gmail.com)" "--warc-header" "furaffinity_scrape_attempt_id: 61527489" "--warc-header" "date: 2025-09-02T20:15:55.001501+00:00" "--warc-header" "furaffinity_submission: 217022" "--warc-header" "program_identity_string: FQDN[fascrape-s-1vcpu-1gb-tor1-24]-PID[555200]-VER[0.2.7]" "--warc-file" "/home/mgrandi/faurls/temp/fa_item_217022_mk1wn889/fascrape_content_sid-217022_aid-61527489" "--recursive" "--level" "1" "--accept-regex" "//[a,d]{1}\.furaffinity\.net/.*|www\.furaffinity\.net/themes/beta/css/.*|www\.furaffinity\.net/themes/beta/img/banners/.*|www\.furaffinity\.net/themes/beta/js/.*" "https://www.furaffinity.net/view/217022/"
operator: Mark Grandi (markgrandi@gmail.com)
furaffinity_scrape_attempt_id: 61527489
date: 2025-09-02T20:15:55.001501+00:00
furaffinity_submission: 217022
program_identity_string: FQDN[fascrape-s-1vcpu-1gb-tor1-24]-PID[555200]-VER[0.2.7]

```