# email-notifier
Sends an Android notification immediately after new email (meeting certain criteria, by sender or subject) is received.

## Business value
Emails that are added to Gmail through POP3/IMAP get the new email forwarded with a ~<1h delay. This program solves the serious issue when an immediate response is required following certain correspondence.

## Development status 
Stable early prototype. Further development: needs refactoring with tests, futhermore, POP3 interface is redundant (should only use IMAP).

## Tech Stack
- Python + IMAP, POP3
- Notifications managed by IFTTT
- Deployed on Heroku

## Deployment in Heroku
Must additionally create config variables `HEROKU` (any value) and `LANG` (value `en_US.UTF-8`)

## Acknowledgements
- https://gist.github.com/jexhson/3496039/
- https://stackoverflow.com/a/31464349/1544154
