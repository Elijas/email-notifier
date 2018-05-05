# email-notifier
Sends an IFTTT (Android) notification immediately after new email (meeting certain criteria, by sender or subject) is received.

## 1. Business value
Emails that are added to Gmail through POP3/IMAP get the new email forwarded with a ~<1h delay. This program solves the serious issue when an immediate response is required following certain correspondence.

## 2. Development status 
Stable early prototype. Further development: needs refactoring with tests, futhermore, POP3 interface is redundant (should only use IMAP).

## 3. Technical details
#### Used Stack
- Python + IMAP, POP3
- Notifications managed by IFTTT
- Deployed on Heroku

#### Deployment in Heroku
Must create config variables from the example and also values `HEROKU` (empty value) and `LANG` (value `en_US.UTF-8`)

#### Acknowledgements and sources
- https://gist.github.com/jexhson/3496039/
- https://stackoverflow.com/a/31464349/1544154
