edux notifier
===

I often forget about my courses so I wrote this little tool to notify me about new announcements.

**WARNING**

You still have to do your homework. Seriously. This script just saves you from checking new stuff on `edux` (and you usually forget to do this).

# License

1. GPL because I really care about your modification if it makes this software better.
2. Beerware if you find it useful.

# Config

## EDUX_USERNAME

Username in `edux` platform.

## EDUX_PASSWORD

Password user for login into `edux` platform.

## MAILGUN_APIKEY

API key to use your `mailgun` platform.

## MAILGUN_DOMAIN

Domain name you will use at `mailgun` 

## EMAIL_SENDER

Who is sending the email.

## EMAIL_RECIPIENT

Who is receiving the email.

# How to run

You want to run it in cron every day if you do not really care. Run it every few hours and you will never miss anything.

# TODO

- Grab quiz data and put into your CalDAV compatible calendar (never miss a quiz)
- Grab exercises data and put into your CalDAV compatible calendar (never miss a deadline on exercises)
