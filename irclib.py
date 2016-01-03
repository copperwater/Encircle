#!/usr/bin/python
import sys
import socket
import string
import time
import datetime
import sched
import ircSettings as sett
import ircVars as v

# Variables that are static to this irclib module.
timeOfLastRemove = time.time()

# Small class to bundle IRC data into an easy to parse format.
class irc:
    prefix = ""
    command = ""
    params = []
    trail = ""

    def __init__(self, p, c, ps, t):
        self.prefix = p;
        self.command = c;
        self.params = ps;
        self.trail = t;

    # If the prefix is user!~server.com or similar, gets "user" from it
    def getName(self):
        return extractName(self.prefix)

# Another class to represent a printable string.
# It has a nick string and a body string. 
class prn:
    strlist = []
    typlist = []
    tstamp = None
    important = False

    def __init__(self, strlist, typlist, important=False):
        self.strlist = strlist
        self.typlist = typlist
        self.tstamp = time.time()
        self.important = important

    # Return the number of extra lines that are needed to print in a terminal
    # horiz characters wide.
    def getOverflowLines(self, horiz):
        # if showing time, there will be an extra "[xx:xx] " (8 chars)
        currlen = 8 if sett.showTime else 0
        lin = 0
        for x in self.strlist:
            if x == '\n':
                # special case, auto cut to next line
                currlen = 0
                lin += 1
                continue
            currlen += len(x)
            if currlen > horiz:
                lin += currlen // horiz
                currlen = currlen % horiz
        return lin

# Class to represent a channel.
class chan:
    # Subclass representing data about a user.
    class user:
        name = ""
        isOp = False
        def __init__(self, name, isOp=False):
            self.name = name; self.isOp = isOp
            
    name = ""
    peopleOn = [] # list of user objects
    msgs = [] # list of prn objects
    isQuery = False # if this is a query window (set of PMs, not a real channel)
    hasUnread = False # if true, the program will notify the user of this
    
    def __init__(self, name, iQ=False):
        self.name = name
        self.peopleOn = []
        self.msgs = []
        self.isQuery = iQ
        self.hasUnread = False

    # Adds a person to peopleOn
    def addUser(self, name):
        op = False
        tmp = name
        if name[0] == '@':
            op = True
            tmp = name[1:]
        self.peopleOn.append(self.user(tmp, op))

    # Removes a person from peopleOn
    def removeUser(self, name):
        for p in self.peopleOn:
            if p.name == name:
                self.peopleOn.remove(p)
                break

    # Determines if the given nick exists in peopleOn
    def nickOn(self, nick):
        if self.isQuery:
            return (self.name == nick)
        for p in self.peopleOn:
            if p.name == nick: return True
        return False

# Library of functions

# Get the current channel name as a string.
def getCurrChannelName():
    return v.chanlist[v.currChannel].name

# Given a channel name, return the index of that channel.
def getChannelNumber(name):
    x = 0
    for c in v.chanlist:
        if c.name == name:
            return x
        x += 1
    return -1

# Get the channel object from its name
def getNamedChannel(name):
    for c in v.chanlist:
        if c.name == name:
            return c

#
# FIND/INSERT/ERASE FUNCTIONS ON THE CHANNEL LIST
# insertChannel, eraseChannel

# Given a channel name, attempt to insert that channel into the list. If it
# already exists, return its number. If it gets inserted, also return its number
# Second argument determines whether this should be marked as a query channel.
def insertChannel(name, isQuery):
    x=0
    for c in v.chanlist:
        if c.name == name:
            return x
        x += 1
    v.chanlist.append(chan(name, isQuery))
    return len(v.chanlist) - 1

# Remove a channel with the given name from the list. (actually all channels)
def eraseChannel(name):
    for c in v.chanlist:
        if c.name == name:
            v.chanlist.remove(c)
            return

#
# FUNCTIONS FOR ADDING MESSAGES TO A CHANNEL
# addChannel, addNumChannel, addCurrChannel, addNamedChannel

# Inserts a new prn object into a given channel.
# Every other add function is a wrapper for this one.
def addChannel(chan, msg):
    # check to see if messages should be deleted
    now = time.time()
    global timeOfLastRemove
    if now - timeOfLastRemove > sett.msgTimeout:
        removeAllOldMessages()
        timeOfLastRemove = now

    chan.msgs.append(msg)
    # make a note that the channel's most recent message came in now
    chan.hasUnread = chan.hasUnread or msg.important
    
# Inserts a new prn object into a numbered channel.
def addNumChannel(num, msg):
    if num > len(v.chanlist):
        # no real defined behavior for this
        pass
    else:
        c = v.chanlist[num]
        addChannel(c, msg)

# Inserts a new prn object into the current channel.
def addCurrChannel(msg):
    addNumChannel(v.currChannel, msg)

# Inserts a new prn object into a channel identified by name.
def addNamedChannel(name, msg):
    x = getChannelNumber(name)
    addNumChannel(x, msg)

#
# FUNCTIONS FOR PARSING RECEIVED IRC MESSAGES
# extractName, isAction, parse

def extractName(st): # take "user" from a string like "user!~server.com"
    return st.split('!')[0]

def isAction(trail): # determines whether trail is an ACTION command
    return ord(trail[0]) == 1 and ord(trail[-1]) == 1

def parse(line): # take a raw line from the server and split into components
    #format of IRC strings is :<prefix> <command> <params> :<trail>
    #get prefix
    prefixStart = 1 if (line[0] == ":") else 0
    prefixEnd = line.find(" ")
    prefix = line[prefixStart:prefixEnd]

    #get trail, which is unique in that it is the first part of the line
    #to begin with " :"
    trailStart = line.find(" :")
    if trailStart > 0:
        commandEnd = trailStart
        trailStart += 2
    else:
        commandEnd = len(line)
        trailStart = len(line)
    trail = line[trailStart:]

    #command and params are between the prefix and trail
    commandStart = prefixEnd+1
    commandString = line[commandStart:commandEnd].split();
    command = commandString[0]
    params = commandString[1:]
        
    return irc(prefix, command, params, trail)
    
# Clear out all outdated messages from all channels.
def removeAllOldMessages():
    now = time.time()
    for c in v.chanlist:
        #c.msgs.append(prn(['Cleanup time'], ['none']))
        ctr = 0
        for msg in c.msgs:
            if now - msg.tstamp < sett.msgTimeout:
                break
            else:
                ctr += 1
        c.msgs = c.msgs[ctr:]
            
# Given a raw message from the server, parse it, format it, and possibly add it
# to the list of strings to be formatted.
def process(msg):
    # If the formatOutput setting is true, do no formatting.
    if sett.formatOutput == False:
        addCurrChannel(prn([msg], ['none']))
        return
        
    # Create the IRC structure from the message
    p = parse(msg)

    extra = False # flag for debugging/unknown messages
    
    if p.command == 'PRIVMSG':
        # params[0] is either channel name or current nick
        if p.params[0] == v.currNick:
            # someone sent a PM directly to the user
            # should open a query window with them
            n = insertChannel(p.getName(), True)
        else:
            # normal message to channel, just get its number
            n = getChannelNumber(p.params[0])
            
        # query or not, the message printout is the same
        # check for /me command formatting
        if p.trail[0] == chr(1) and p.trail[-1] == chr(1):
            addNumChannel(n, prn([p.getName(), p.trail[7:-1]],
                                 ['nick', 'none'], True))
        else:
            addNumChannel(n, prn(['<' + p.getName() + '> ', p.trail],
                                 ['nick', 'none'], True))

    elif p.command == 'NICK':
        # This should autoscan all active channel name lists and place the
        # changed nick message in any channel that the previous name was on

        # The IRC protocol does not play nice with people changing their
        # nick while in a query window. The other person is not notified unless
        # both parties are also on the same channel.
        # In my experience, this rarely comes up in practice. This should,
        # however, be smart enough to change the name of any query windows that
        # match the name of the nick being changed.
        n = p.getName()
        newNick = p.trail
        if p.trail == '':
            newNick = p.params[0]
        if n == v.currNick:
            v.currNick = newNick
            # The user is in all channels, so every non-query channel should
            # be notified
            for c in v.chanlist:
                if c.isQuery: continue
                addChannel(c, prn(['You', ' changed nick to ', newNick],
                                  ['you', 'notice', 'you']))
        else:
            msg = prn([n, ' changed nick to ', newNick],
                      ['nick', 'notice', 'nick'], True)
            for c in v.chanlist:
                if c.isQuery and c.name == n:
                    # change query name to the new nick
                    c.name = newNick
                    addChannel(c, msg)
                elif c.nickOn(n):
                    # If the other person is on any same channels, switch out
                    # their nickname.
                    c.removeUser(n)
                    c.addUser(newNick)
                    addChannel(c, msg)
        
    elif p.command == 'JOIN':
        n = p.getName()
        if len(p.params) == 0:
            chName = p.trail
            # no params? Try the trail
        else:
            chName = p.params[0]
            
        if n == v.currNick:
            # you joined, create new channel and log to that channel
            cn = insertChannel(chName, False)
            v.currChannel = cn
            addCurrChannel(prn(['You', ' joined ', chName],
                               ['you', 'notice', 'channel']))
        else:
            # new person joined, report it to channel and add name to list
            c = v.chanlist[getChannelNumber(chName)]
            c.addUser(n)
            addChannel(c, prn([n, ' joined ', chName],
                              ['nick', 'notice', 'channel']))

    elif p.command == 'PART':
        n = p.getName()
        if n == v.currNick:
            # You left the channel, do no logging, delete the channel window
            # Ideally this should revert to the most recently used channel
            eraseChannel(p.params[0])
            v.currChannel = 0
            addNumChannel(0, prn(['You', ' left ', p.params[0]],
                                 ['you', 'notice', 'channel']))
        else:
            # Someone else left the channel, delete them from the list of users
            c = getNamedChannel(p.params[0])
            c.removeUser(n)
            addChannel(c, prn([n, ' left ', p.params[0]],
                              ['nick', 'notice', 'channel']))

    elif p.command == 'QUIT':
        # You never get a QUIT for yourself.
        n = p.getName()
        for c in v.chanlist:
            if c.nickOn(n):
                c.removeUser(n)
                addChannel(c, prn([p.getName(), ' has quit: ', p.trail],
                                  ['nick', 'notice', 'notice']))
        
    elif p.command == 'NOTICE':
        # Notices can be sent to a user or channel, just like PRIVMSGs.
        if p.params[0] == v.currNick:
            c = 0
        else:
            c = getChannelNumber(p.params[0])
            
        addNumChannel(c, prn([p.getName(), ' notice: ' + p.trail],
                             ['nick', 'notice'], True))
        
    elif p.command == 'MODE':
        # Known kinds of MODE responses:
        # :me MODE me :+i
        # :server MODE #chan +ns
        # :user!~userhost MODE #chan +m
        # :user!~userhost MODE #chan +v person
        
        # important only if it affects the user
        target = p.params[0]
        important = (target == v.currNick)
            
        if len(p.trail) > 0:
            addNumChannel(0, prn([target, ' mode change: ', p.trail],
                                 ['nick', 'notice', 'notice'], important))
            return
        else:
            # all the other change mode types are channel-based
            # the rest of this is just to construct the message and log it
            src = p.getName(); mode = 'nick'
            if src == v.currNick:
                src = 'You'; mode = 'you'

            target = p.params[0]; tmode = 'channel'
            if len(p.params) == 3:
                target = p.params[2]; tmode = 'nick'
                if target == v.currNick:
                    important = True
                    tmode = 'you'

            msg = prn([src, ' changed mode of ', target, ': ', p.params[1]],
                      [mode, 'notice', tmode, 'notice', 'notice'], important)
                
            addNamedChannel(p.params[0], msg)

    elif p.command == 'TOPIC':
        # just log the change in topic
        addNamedChannel(p.params[0],
                        prn([p.getName(), ' changed the topic of ', p.params[0], ' to ', p.trail],
                            ['nick', 'notice', 'channel', 'notice', 'none']))

    elif p.command == 'KICK':
        # The kickee and channel written to vary depending on who got kicked.
        tmp = p.params[1]; mode = 'nick'; n = getChannelNumber(p.params[0])
        # Not important unless you got kicked
        important = False
        
        if tmp == v.currNick:
            # If you got kicked, the channel is deleted and 0 gets logged to.
            eraseChannel(p.params[0])
            v.currChannel = 0; n = 0
            tmp = 'You'; mode = 'you'
            important = True
            
        # Whoever got kicked, log it.
        addNumChannel(n, prn([tmp, ' got kicked out of ', p.params[0], ' by ',
                              p.getName(), ': ', p.trail],
                             [mode, 'notice', 'channel', 'notice', 'nick',
                              'notice', 'none'],
                             important))
        
    elif p.command == 'INVITE':
        # Just log it in the default window.
        addNumChannel(0, prn([p.getName(), ' invites you to ', p.trail],
                             ['nick', 'notice', 'channel'], True))

    #
    # The following (the numeric codes) are largely just logging stuff, maybe
    # with some condition. A few will have more complex behavior.
    
    elif p.command == '001': # welcome
        addNumChannel(0, prn([p.trail], ['notice']))
        
    elif p.command == '002': # your host is
        if not sett.hideServerStats:
            addNumChannel(0, prn([p.trail], ['notice']))
        
    elif p.command == '003': # server creation timestamp
        if not sett.hideServerStats:
            addNumChannel(0, prn([p.trail], ['notice']))

    elif p.command == '004': # server version and permitted user/channel modes
        if not sett.hideServerStats:
            addNumChannel(0, prn([p.trail], ['notice']))

    elif p.command == '005': # server supported list
        if not sett.hideServerStats:
            addNumChannel(0, prn([p.trail], ['notice']))

    elif p.command == '042': # your id
        addNumChannel(0, prn(['Your unique ID is ' + p.params[1]], ['notice']))

    elif p.command == '219': # end of server stats
        if not (sett.disregard or sett.hideServerStats):
            addCurrChannel(prn(['End of stats report.'],['notice']))

    elif p.command == '242': # stats server uptime
        if not sett.hideServerStats:
            addCurrChannel(prn([p.trail], ['notice']))
        
    elif p.command == '250': # connection stats
        if not sett.hideServerStats:
            addNumChannel(0, prn([p.trail], ['notice']))
        
    elif p.command == '251': # total users/servers
        if not sett.hideServerStats:
            addNumChannel(0, prn([p.trail], ['notice']))
        
    elif p.command == '252': # operators online
        if not sett.hideServerStats:
            addNumChannel(0, prn([p.params[1]+' operators online'], ['notice']))
        
    elif p.command == '253': # unknown connections
        if not sett.hideServerStats:
            addNumChannel(0, prn([p.params[1]+' unknown connections'],
                                 ['notice']))
        
    elif p.command == '254': # number of channels
        if not sett.hideServerStats:
            addNumChannel(0, prn([p.params[1]+' channels'], ['notice']))
        
    elif p.command == '255': # number clients/servers
        if not sett.hideServerStats:
            addNumChannel(0, prn([p.trail], ['notice']))

    elif p.command == '256': # administrative info announcement
        addNumChannel(0, prn([p.trail], ['notice']))

    elif p.command == '257': # admin announcement 1
        addNumChannel(0, prn([p.trail], ['notice']))

    elif p.command == '258': # admin announcement 2
        addNumChannel(0, prn([p.trail], ['notice']))

    elif p.command == '259': # admin email
        addNumChannel(0, prn([p.trail], ['notice']))

    elif p.command == '263': # server dropped command without completing it
        addCurrChannel(prn([p.params[1], ': ', p.trail],
                           ['error', 'error', 'error']))
        
    elif p.command == '265': # local users nonstandard
        if not (sett.hideServerStats or sett.ignoreNonstandard):
            addNumChannel(0, prn([p.trail], ['notice']))
        
    elif p.command == '266': # global users nonstandard
        if not (sett.hideServerStats or sett.ignoreNonstandard):
            addNumChannel(0, prn([p.trail], ['notice']))

    elif p.command == '301': # other user is away
        addCurrChannel(prn(['Note that ', p.params[1], ' is away'],
                       ['notice', 'nick', 'notice']))

    elif p.command == '305': # now not marked as away
        addCurrChannel(prn(['You are no longer marked as being away'],
                           ['notice']))
        
    elif p.command == '306': # now marked as away
        addCurrChannel(prn(['You are now marked as being away'], ['notice']))

    elif p.command == '307': # is a registered nick
        addCurrChannel(prn([p.params[1], ' is a registered nick'], ['nick', 'error']))

    elif p.command == '311': # whois reply, user section
        addCurrChannel(prn(['WHOIS ', p.params[1], '\n', 'realname = ', p.trail,
                            '\n', 'user = ', p.params[2], '\n', 'host = ',
                            p.params[3]],
                           ['notice', 'nick', 'none', 'notice', 'none', 'none',
                            'notice', 'none', 'none', 'notice', 'none']))

    elif p.command == '312': # whois reply, server the user is on
        addCurrChannel(prn([p.params[1], ' is on server ', p.params[2]],
                           ['nick', 'notice', 'notice']))

    elif p.command == '314': # whowas reply, user section
        addCurrChannel(prn(['WHOWAS ', p.params[1], '\n', 'realname = ', p.trail,
                            '\n', 'user = ', p.params[2], '\n', 'host = ',
                            p.params[3]],
                           ['notice', 'nick', 'none', 'notice', 'none', 'none',
                            'notice', 'none', 'none', 'notice', 'none']))

    elif p.command == '317': # seconds idle and signon time
        tstr = datetime.datetime.fromtimestamp(int(p.params[3])
                                               ).strftime("%Y-%m-%d %H:%M:%S")
        addCurrChannel(prn([p.params[1], ' has been idle for ', p.params[2],
                            ' seconds and signed on at ', tstr],
                           ['nick', 'notice', 'notice', 'notice', 'notice']))

    elif p.command == '318': # end of whois list
        if not sett.disregard:
            addCurrChannel(prn(['End of whois list'],['notice']))

    elif p.command == '319': # whois reply, channels the user is on
        addCurrChannel(prn([p.params[1], ' is on channels ', p.trail],
                           ['nick', 'notice', 'notice']))

    elif p.command == '321': # beginning of channel list
        if not sett.disregard:
            addNumChannel(0, prn(['Beginning of channel list'], ['notice']))
            v.currChannel = 0

    elif p.command == '322': # channel list
        addNumChannel(0, prn([p.params[1], ' (', p.params[2], ' users): ',
                              p.trail],
                             ['channel', 'notice', 'notice', 'notice', 'none'],
                             True))

    elif p.command == '323': # end of channel list
        if not sett.disregard:
            addNumChannel(0, prn(['End of channel list'], ['notice']))

    elif p.command == '324': # current channel modes
        addNamedChannel(p.params[1], prn([p.params[1], ' modes: ', p.params[2]],
                                         ['channel', 'notice', 'notice']))

    elif p.command == '328': # channel URL
        addNamedChannel(p.params[1], prn([p.params[1], ' ', p.trail],
                                         ['channel', 'none', 'none']))

    elif p.command == '329': # channel creation time
        addNamedChannel(p.params[1], prn([p.params[1], ' was created at ',
                                          p.params[2]],
                                         ['channel', 'notice', 'notice']))

    elif p.command == '330': # nonstandard logged in as
        if not sett.ignoreNonstandard:
            addCurrChannel(prn([p.params[1], ' is logged in as ', p.params[2]],
                               ['nick', 'notice', 'notice']))
        
    elif p.command == '332': # channel topic
        addNamedChannel(p.params[1], prn(['Topic: ', p.trail],
                                         ['notice', 'none']))

    elif p.command == '333': # who, from where, and when the topic was set
        addNamedChannel(p.params[1],
                        prn(['Topic set by ', extractName(p.params[2])],
                            ['notice', 'nick']))

    elif p.command == '341': # invite sent successfully
        addNamedChannel(p.params[2],
                        prn(['Invited ', p.params[1], ' to ', p.params[2]],
                            ['notice', 'nick', 'notice', 'channel']))
        
    elif p.command == '353': # names list
        # reset the names of people in the channel
        x = getChannelNumber(p.params[2])
        c = v.chanlist[x]
        c.peopleOn = []
        namelist = p.trail.split()
        for n in namelist:
            c.addUser(n)
        addChannel(c, prn(['Names: ', p.trail],
                          ['notice', 'nick']))

    elif p.command == '366': # end of names list
        if not sett.disregard:
            addCurrChannel(prn(['End of names list'],['notice']))

    elif p.command == '368': # end of channel ban list
        if not sett.disregard:
            addCurrChannel(prn(['End of channel ban list'],['notice']))

    elif p.command == '369': # end of whowas list
        if not sett.disregard:
            addCurrChannel(prn(['End of whowas list'],['notice']))
                     
    elif p.command == '372': # motd body
        if not sett.hideMOTD:
            addNumChannel(0, prn([p.trail],['notice']))

    elif p.command == '375': # motd header
        if not (sett.disregard or sett.hideMOTD):
            addCurrChannel(prn(['Beginning of MOTD'],['notice']))

    elif p.command == '376': # end of motd 
        if not (sett.disregard or sett.hideMOTD):
            addCurrChannel(prn(['End of MOTD'],['notice']))

    elif p.command == '378': # freenode nonstandard whois host response
        if not sett.ignoreNonstandard:
            addCurrChannel(prn([p.params[1], ' ', p.trail],
                               ['nick', 'notice', 'notice']))

    elif p.command == '379': # nonstandard whois modes
        if not sett.ignoreNonstandard:
            addCurrChannel(prn([p.params[1], ' ', p.trail],
                               ['nick', 'notice', 'notice']))

    elif p.command == '401': # no such nick
        addCurrChannel(prn([p.params[1] + ': No such nick'], ['error']))

    elif p.command == '402': # no such server
        addCurrChannel(prn([p.params[1] + ': No such server'], ['error']))
        
    elif p.command == '403': # no such channel
        addCurrChannel(prn([p.params[1] + ': No such channel'], ['error']))

    elif p.command == '404': # cannot send to channel (no voice, etc)
        addCurrChannel(prn(['Cannot send to channel ' + p.params[1]],
                           ['error', 'error']))

    elif p.command == '406': # there was no such nick
        addCurrChannel(prn([p.params[1] + ' never existed'], ['error']))

    elif p.command == '411': # no recipient
        addCurrChannel(prn(['No recipient given'], ['error']))
        
    elif p.command == '412': # no text to send
        addCurrChannel(prn(['No text to send'], ['error']))

    elif p.command == '421': # unknown command
        addCurrChannel(prn(['Unknown command'], ['error']))

    elif p.command == '432': # erroneous nickname
        addCurrChannel(prn(['Erroneous nickname ', p.params[1]],
                           ['error', 'error']))

    elif p.command == '433': # nickname already in use
        addCurrChannel(prn(['Nickname ', p.params[1], ' is already in use.'],
                           ['error', 'nick', 'error']))

    elif p.command == '442': # not on channel
        addCurrChannel(prn(["You're not on ", p.params[1]],
                           ['error', 'error']))

    elif p.command == '443': # already on channel
        addCurrChannel(prn(["You're already on ", p.params[1]],
                           ['error', 'error']))

    elif p.command == '461': # not enough parameters
        addCurrChannel(prn([p.params[1], ': Not enough parameters'],
                           ['error', 'error']))

    elif p.command == '462': # already registered
        addCurrChannel(prn(['You have already signed in'], ['error']))

    elif p.command == '470': # forwarding you to another channel
        addNumChannel(0, prn(["Forwarding you from ", p.params[1], ' to ',
                              p.params[2]],
                             ['notice','notice','notice','notice']));

    elif p.command == '471': # channel is full
        addCurrChannel(prn([p.params[1], ' is full'],
                           ['error', 'error']))
        
    elif p.command == '472': # unknown mode
        addCurrChannel(prn(['Unknown mode character: ', p.params[1]],
                           ['error', 'error']))

    elif p.command == '473': # channel is invite only
        addCurrChannel(prn(['Channel ', p.params[1], ' is invite-only'],
                           ['notice', 'channel', 'notice']))

    elif p.command == '481': # not enough privileges
        addCurrChannel(prn([p.trail], ['error']))
        
    elif p.command == '482': # privileges needed
        addCurrChannel(prn([p.trail], ['error']))

    elif p.command == '501': # unknown mode flag
        addCurrChannel(prn(['Unrecognized mode flag'], ['error']))

    elif p.command == '502': # can't see or change mode of other users
        addCurrChannel(prn(["You can't see or change the mode of other users"],
                           ['error']))

    elif p.command == '524': # help page not found
        addCurrChannel(prn([p.params[1], ' help page not found'],
                           ['error'],['error']))

    elif p.command == '671': # nonstandard is using a secure connection
        if not sett.ignoreNonstandard:
            addCurrChannel(prn([p.params[1], ' ' + p.trail],
                               ['nick', 'notice']))
                       
    elif p.command == '704': # help header
        addCurrChannel(prn([p.trail], ['notice']))

    elif p.command == '705': # help body
        addCurrChannel(prn([p.trail], ['notice']))

    elif p.command == '706': # end of help
        if not sett.disregard:
            addCurrChannel(prn([p.trail],['notice']))

    elif p.command == '900': # you are now logged in
        addNumChannel(0, prn(['You are now logged in as ', p.params[0]],
                             ['notice', 'you']))

    elif p.command == 'PONG': # user sent a ping request, I don't know why
        addNumChannel(0, 'PONG') 

    else:
        extra = True
        
    if extra:
        addCurrChannel(prn([msg],['none']))
