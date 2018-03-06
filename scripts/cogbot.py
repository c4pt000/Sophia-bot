#!/usr/bin/env python2.7


import sys #List of pre-made libararies to import
import socket
import string
import re
import os
import sys
import logging
import threading
from time import sleep
from client import *

safe = ['c4pt'] #Users that can control the bots actions

#Global Variables
host="192.168.122.237" #This is the IRC server variable. 
port=6667 #This is the port
nick="cogbot" #Bot name
ident="cogbot" #ID to NickServ with this name
realname="cogbot" #Bots real name for server identification 
channel="#null" #This is the channel name







s=socket.socket(socket.AF_INET, socket.SOCK_STREAM, socket.IPPROTO_TCP ) #Creates a new socket
s.connect((host, port)) #Connect to the host IRC network through port 6667
s.sendall("NICK %s\r\n" % nick) #Sets the Bot's nick name
s.sendall("USER %s %s bla :%s\r\n" % (ident, host, realname)) #Logs Bot into IRC and ID's
s.send("JOIN :%s\r\n" % channel) #Join #nullbytez
s.send("NOTICE %s :%s\r\n" % (channel, "-ola")) #Send messages to channel
s.send("PRIVMSG %s :%s\r\n"% (channel, "we are here"))


self.ask('hi')

f =s.makefile()
while 1: #Loop forever because 1 == always True (keeps us connected to IRC)
    line = f.readline().rstrip() #New readline for buffer

    print line

    if re.search(".*\001.*\001.*", line): #This block searches chan msgs for strings
        user = line.split('!~')[0][1:]
        s.sendall('PRIVMSG {0} :stop plox\r\n'.format(user))
    else:
        if '!quit' in line: #If a user PRIVMSG's '!quit' quit
            s.sendall("QUIT :Quit: Leaving..\r\n")
            break
            
        if '!op' in line:
            user = line[line.find('!op')+len('!op'):].rstrip().lstrip()
            if user in safe:
                s.sendall("MODE {0} +o {1}\r\n".format(channel, user))
                
        if 'PING' in line: #If the server pings, ping back (keeps connection)
            msg = line.split(':')[1].lstrip().rstrip()
            s.sendall("PONG {0}\r\n".format(msg))


	if "PRIVMSG" in line and channel in line and "cogbot" in line:
               s.send("PRIVMSG %s :%s\r\n"% (channel, "hello"))
	       line = re.sub(r"^[^,]*,", "", line)
	       print line
#	       self.ask('line')

#	       print line
#	       print line
#	       print line
#	       print line
#	       print line
	




