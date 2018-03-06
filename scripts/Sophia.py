#!/usr/bin/env python2.7

import os

from twisted.internet import protocol, reactor
from twisted.words.protocols import irc

from client import Client

HR_CHATBOT_AUTHKEY = os.environ.get('HR_CHATBOT_AUTHKEY', 'AAAAB3NzaC')


class IRCLogger(irc.IRCClient):
    def __init__(self, *args, **kwargs):
        self.nickname = 'Sophia-bot'
        self.cog_client = Client(HR_CHATBOT_AUTHKEY)
        self.prefix = self.nickname + ', '

    def signedOn(self):
        self.join('#null')

    def privmsg(self, user, channel, message):
        print "Got msg %s " % message

        if message.startswith(self.prefix):
            message = message[len(self.prefix):]
            response = self.cog_client.ask(message)
	    self.msg(channel, str(response['text']))

def main():
    f = protocol.ReconnectingClientFactory()
    f.protocol = IRCLogger
    reactor.connectTCP('moon.freenode.net', 6667, f)
    reactor.run()


if __name__ == '__main__':
    main()

