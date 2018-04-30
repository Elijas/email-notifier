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
import threading
import sys
import codecs

import time

import signal

sys.stdout = codecs.getwriter('utf8')(sys.stdout)
sys.stderr = codecs.getwriter('utf8')(sys.stderr)


class _Config:
    POP3_SERVER = None
    IMAP_SERVER = None
    EMAIL_USER = None
    EMAIL_PASSWORD = None
    EMAIL_SEARCH_DEPTH = None
    IMPORTANT_EMAIL_SENDERS = None
    IMPORTANT_EMAIL_SUBJECTS = None
    IFTTT_WEBHOOK_URLS = None
    IFTTT_NOTIFICATIONS_LIMIT = None
    IFTTT_WEBHOOK_ADMIN_URLS = None
    SEND_TEST_NOTIFICATION = None

    def __init__(self):
        for key in [a for a in dir(self) if not a.startswith('__') and not callable(getattr(self, a))]:
            if 'HEROKU' in os.environ:
                setattr(self, key, os.environ[key])
            else:
                import configVals
                setattr(self, key, getattr(configVals, key))


config = _Config()

prevEmailTimestamp = "Sat, 01 Jan 2000 00:00:00 +0000"
prevEmailTimestampTempNew = None


def sendNotification(title='', text='', txtPrefix='Notification', urlsString=config.IFTTT_WEBHOOK_URLS):
    urls = urlsString.split('|')
    deliveryStatuses = []
    for url in urls:
        r = requests.post(url, data={'value1': title, 'value2': text, })
        deliveryStatuses.append('{} {}'.format(r.status_code, r.reason))
    print('{} sent [{}]: {} | {}'.format(txtPrefix, ', '.join(deliveryStatuses), title, text))


def sendAdminNotificationAndPrint(title='', text=''):
    sendNotification(title=title, text=text, txtPrefix='Admin Notif.', urlsString=config.IFTTT_WEBHOOK_ADMIN_URLS)


def decodeMimeText(s):
    mimeTextEncodingTuples = email.header.decode_header(s)
    return ' '.join(
        (m[0].decode(m[1]) if m[1] is not None else (m[0].decode('utf-8') if hasattr(m[0], 'decode') else str(m[0])))
        for m in mimeTextEncodingTuples)


def searchNewestEmail(notificationLimit=int(config.IFTTT_NOTIFICATIONS_LIMIT), sendOnlyTestNotif=False):
    global prevEmailTimestamp, prevEmailTimestampTempNew
    server = poplib.POP3(config.POP3_SERVER)
    server.user(config.EMAIL_USER)
    server.pass_(config.EMAIL_PASSWORD)

    # list items on server
    resp, items, octets = server.list()

    L = len(items)
    searchLimit = int(config.EMAIL_SEARCH_DEPTH)

    sentNotifications = 0
    for i in reversed(range(max(0, L - searchLimit), L)):
        s = items[i].decode("utf-8")
        id, size = s.split(' ')
        resp, text, octets = server.top(id, 0)
        # because server.retr(id) trips seen flag, server.top(...) doesn't,
        # and also (POSSIBLY?) double-triggers event (first - message received, second - a message is read)
        # NOTE: .top(...) is poorly specified in RFC, therefore might be buggy depending on server

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

                if sendOnlyTestNotif:
                    sendNotification('Email notifier STARTED!',
                                     'EXAMPLE EMAIL: ' + subject + ', ' + sender + ', ' + newEmailTimestamp)
                    break

                if sentNotifications < notificationLimit:
                    sendNotification(subject, sender + ', "' + newEmailTimestamp + '", (' + subject + ')')
                    sentNotifications += 1
                    if sentNotifications >= notificationLimit:
                        print('END: Further search stopped due to reached notification limit of {}'
                              .format(notificationLimit))
                        break
                elif notificationLimit == 0:
                    break
            else:
                if sentNotifications == 0:
                    print('No important emails since the last one at "{}"'.format(prevEmailTimestamp))
                else:
                    print(
                        'END: Further search stopped due to a depth limit of "{}"'.format(prevEmailTimestamp))
                break
    if prevEmailTimestampTempNew is not None:
        prevEmailTimestamp = prevEmailTimestampTempNew
        prevEmailTimestampTempNew = None


# This is the threading object that does all the waiting on
# the event
class IMAPListener(object):
    def __init__(self, conn):
        self.thread = threading.Thread(target=self.idle)
        self.M = conn
        self.event = threading.Event()

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
    def dosync(self):  # Gets triggered on new email event, but also periodically without (?) email events
        searchNewestEmail()


class GracefulKiller:
    kill_now = False

    def __init__(self):
        signal.signal(signal.SIGINT, self.exit_gracefully)
        signal.signal(signal.SIGTERM, self.exit_gracefully)

    def exit_gracefully(self, signum, frame):
        print("Caught kill signal: {}".format(signum))
        self.kill_now = True

    def sleep(self, timeout_s):
        for _ in range(timeout_s):
            time.sleep(1)
            if self.kill_now:
                break


imapListener = None
imapClient = None
killer = GracefulKiller()

_sendTestNotification = bool(int(config.SEND_TEST_NOTIFICATION))
while True:
    try:
        try:
            imapClient = imaplib2.IMAP4_SSL(config.IMAP_SERVER, timeout=60 * 28)  # Default timeout is 29min=None=60*29)
            imapClient.login(config.EMAIL_USER, config.EMAIL_PASSWORD)
            imapClient.select("INBOX")  # We need to get out of the AUTH state, so we just select the INBOX.
            imapListener = IMAPListener(imapClient)  # Start the Idler thread
            imapListener.start()
            print('IMAP listening has started')

            # Helps update the timestamp, so that on event only new emails are sent with notifications
            searchNewestEmail(notificationLimit=0, sendOnlyTestNotif=_sendTestNotification)
            _sendTestNotification = False

            reconnectTimeout_s = 60 * 60 * 24 * 1
            killer.sleep(reconnectTimeout_s)
            if not killer.kill_now:
                print("Refreshing IMAP connection. timeout={}s".format(reconnectTimeout_s))
        finally:
            if imapListener is not None:
                imapListener.stop()  # Had to do this stuff in a try-finally, since some testing went a little wrong..
                imapListener.join()
            if imapClient is not None:
                imapClient.close()
                imapClient.logout()  # This is important!
            print('IMAP listening has stopped, conn cleanup was run for: Listener: {}, Client: {}'
                  .format(imapListener is not None, imapClient is not None))
            sys.stdout.flush()  # probably not needed

            if killer.kill_now:
                break
    except imaplib2.IMAP4.abort as e:
        retryDelay_s = 30
        sendAdminNotificationAndPrint("Conn error, retrying in {}s".format(retryDelay_s), str(e))
        killer.sleep(retryDelay_s)
