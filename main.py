# coding=utf-8
from __future__ import unicode_literals
import poplib
import email
import email.parser
import email.header
import dateutil.parser
import requests
import imaplib2
import os
from threading import *
import sys
import codecs

import time

sys.stdout = codecs.getwriter('utf8')(sys.stdout)
sys.stderr = codecs.getwriter('utf8')(sys.stderr)


class _Config:
    POP3_SERVER = None
    IMAP_SERVER = None
    EMAIL_USER = None
    EMAIL_PASSWORD = None
    EMAIL_SEARCH_DEPTH = None
    INITIAL_PREV_EMAIL_TIMESTAMP = None
    IMPORTANT_EMAIL_SENDERS = None
    IMPORTANT_EMAIL_SUBJECTS = None
    IFTTT_WEBHOOK_URLS = None
    IFTTT_NOTIFICATIONS_LIMIT = None

    def __init__(self):
        for key in [a for a in dir(self) if not a.startswith('__') and not callable(getattr(self, a))]:
            if 'HEROKU' in os.environ:
                setattr(self, key, os.environ[key])
            else:
                import configVals
                setattr(self, key, getattr(configVals, key))


config = _Config()

prevEmailTimestamp = config.INITIAL_PREV_EMAIL_TIMESTAMP
prevEmailTimestampTempNew = None

sentNotifications = 0


def sendNotification(subject='', sender=''):
    for url in config.IFTTT_WEBHOOK_URLS.split('|'):
        r = requests.post(url, data={'value1': subject, 'value2': sender, })
        print('Notification sent: {} {}'.format(r.status_code, r.reason))


def decodeMimeText(s):
    mimeTextEncodingTuples = email.header.decode_header(s)
    return ' '.join(
        (m[0].decode(m[1]) if m[1] is not None else (m[0].decode('utf-8') if hasattr(m[0], 'decode') else str(m[0])))
        for m in mimeTextEncodingTuples)


def searchNewestEmail(searchLimit=None):
    global prevEmailTimestamp, prevEmailTimestampTempNew, sentNotifications
    server = poplib.POP3(config.POP3_SERVER)
    server.user(config.EMAIL_USER)
    server.pass_(config.EMAIL_PASSWORD)

    # list items on server
    resp, items, octets = server.list()

    L = len(items)
    if searchLimit is None:
        searchLimit = int(config.EMAIL_SEARCH_DEPTH)
    for i in reversed(range(max(0, L - searchLimit), L)):
        s = items[i].decode("utf-8")
        id, size = s.split(' ')
        resp, text, octets = server.retr(id)

        text = '\n'.join(t.decode("ascii", 'ignore') for t in text)

        message = email.message_from_string(text)

        d = dict(message.items())

        subject = decodeMimeText(d['Subject'])
        sender = decodeMimeText(d['From'])

        isImportantSender = any(
            importantEmailSender in sender for importantEmailSender in config.IMPORTANT_EMAIL_SENDERS.split('|'))
        isImportantSubject = any(
            importantSubject in subject.lower() for importantSubject in
            config.IMPORTANT_EMAIL_SUBJECTS.lower().split('|'))

        if (isImportantSender or isImportantSubject):
            newEmailTimestamp = d['Date']
            newEmailDate = dateutil.parser.parse(newEmailTimestamp)
            prevEmailDate = dateutil.parser.parse(prevEmailTimestamp)
            if newEmailDate > prevEmailDate:
                if prevEmailTimestampTempNew is None:
                    prevEmailTimestampTempNew = newEmailTimestamp

                if sentNotifications < int(config.IFTTT_NOTIFICATIONS_LIMIT):
                    print('Found important email: "{}" from "{}" at "{}"'.format(subject, sender, newEmailTimestamp))
                    sendNotification(subject, sender)
                    sentNotifications += 1
                    if sentNotifications == int(config.IFTTT_NOTIFICATIONS_LIMIT):
                        print('Limit of {} sent notifications is reached'.format(config.IFTTT_NOTIFICATIONS_LIMIT))
                        break
            else:
                print('Limit of "{}" email date is reached'.format(prevEmailTimestamp))
                break
    if prevEmailTimestampTempNew is not None:
        prevEmailTimestamp = prevEmailTimestampTempNew
    prevEmailTimestampTempNew = None


# This is the threading object that does all the waiting on
# the event
class IMAPListener(object):
    def __init__(self, conn):
        self.thread = Thread(target=self.idle)
        self.M = conn
        self.event = Event()

    def start(self):
        self.thread.start()

    def stop(self):
        # This is a neat trick to make thread end. Took me a
        # while to figure that one out!
        self.event.set()

    def join(self):
        self.thread.join()

    def idle(self):
        # Starting an unending loop here
        while True:
            # This is part of the trick to make the loop stop
            # when the stop() command is given
            if self.event.isSet():
                return
            self.needsync = False

            # A callback method that gets called when a new
            # email arrives. Very basic, but that's good.
            def callback(args):
                if not self.event.isSet():
                    self.needsync = True
                    self.event.set()

            # Do the actual idle call. This returns immediately,
            # since it's asynchronous.
            self.M.idle(callback=callback)
            # This waits until the event is set. The event is
            # set by the callback, when the server 'answers'
            # the idle call and the callback function gets
            # called.
            self.event.wait()
            # Because the function sets the needsync variable,
            # this helps escape the loop without doing
            # anything if the stop() is called. Kinda neat
            # solution.
            if self.needsync:
                self.event.clear()
                self.dosync()

    # The method that gets called when a new email arrives.
    # Replace it with something better.
    def dosync(self):
        print("Received new email")
        sys.stdout.flush()  # probably not needed
        searchNewestEmail()


# Had to do this stuff in a try-finally, since some testing
# went a little wrong.....
imapListener = None
imapClient = None
try:
    # Set the following two lines to your creds and server
    imapClient = imaplib2.IMAP4_SSL(config.IMAP_SERVER)
    imapClient.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
    # We need to get out of the AUTH state, so we just select
    # the INBOX.
    imapClient.select("INBOX")
    # Start the Idler thread
    imapListener = IMAPListener(imapClient)
    imapListener.start()
    print('IMAP listening has started')

    sendNotification(subject='Email notifier is started', sender='You will now receive a sample notification')

    # Helps update the timestamp, so that on event only new emails are sent with notifications
    searchNewestEmail(searchLimit=1)

    for _ in range(92):  # 92 days = 3 Months
        time.sleep(86400)  # 86400s = 1 Day

    sendNotification(subject='Notifier is stopped', sender='Email notifier system has been stopped')
finally:
    # Clean up.
    if imapListener is not None:
        imapListener.stop()
        imapListener.join()
    if imapClient is not None:
        imapClient.close()
        # This is important!
        imapClient.logout()
    print('IMAP listening is stopped')
    sys.stdout.flush()  # probably not needed
