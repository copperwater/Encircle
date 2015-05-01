#!/usr/bin/env python

import curses
import sys
import irclib
import socket
import select
import signal
import ircSettings as sett
import ircVars as v
import time
import errno

# Client globals
dimensions = []
inputStr = ''
s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
nameWidth = 12
scrollPos = 0

# Resets the window after user input or update
def redraw():       
    window.clear()
    global dimensions
    dimensions = window.getmaxyx()     #refresh dimensions

    # Base header bar
    window.addstr(0, 0, ' '*dimensions[1], stylemap['header'])
    # Server
    window.addstr(0, 0, v.server, stylemap['header'])
    currlen = len(v.server)
    window.addstr(0, currlen, ' - ', stylemap['header'])
    currlen += 3
    # Current channel/query
    chanName = v.chanlist[v.currChannel].name
    window.addstr(0, currlen, ' '+chanName+' ',stylemap['channelHeader'])
    currlen += len(chanName)+2
    window.addstr(0, currlen, ' - ', stylemap['header'])
    # Current nick
    if v.currNick != '':
        currlen += 3
        window.addstr(0, currlen, ' '+v.currNick+' ', stylemap['youHeader'])
    # Unread message alert
    anyUnread = False
    for x in range(0, len(v.chanlist)):
        if v.currChannel == x:
            v.chanlist[x].hasUnread = False
        elif v.chanlist[x].hasUnread:
            anyUnread = True
    if anyUnread:
        window.addstr(0, dimensions[1]-4, ' ! ', stylemap['notification'])


    # Calculate the number of lines in the user input line
    inputVertical = len(inputStr) // dimensions[1]
        
    # Print strings backwards from bottom line
    chanList = v.chanlist[v.currChannel].msgs
    strpos = dimensions[0] - 3 - inputVertical
    scrollCtr = 0
    for prn in reversed(chanList):
        # Skip the (scrollPos) latest messages
        if scrollCtr < scrollPos:
            scrollCtr += 1
            continue
            
        # Subtract the number of overflow lines from strpos
        strpos -= prn.getOverflowLines(dimensions[1])

        # do not overwrite header
        if strpos < 1:
            break

        # position the cursor at the start of the correct line
        # curses.setsyx() doesn't work here for some reason
        window.addstr(strpos, 0, '')

        # iterate through the formatting and write out everything
        if v.showTime:
            window.addstr('[' + time.strftime('%H:%M', prn.tstamp) + '] ',
                          stylemap['time'])
        tmpstrpos = strpos
        for st, ty in zip(prn.strlist, prn.typlist):
            if st == '\n':
                tmpstrpos += 1
                window.addstr(tmpstrpos, 0, '') #curses.setsyx(tmpstrpos,0)
                continue
            if st.isspace(): continue
            
            window.addstr(st, stylemap[ty])
        strpos -= 1

    # Print bottom line
    for x in range(0, dimensions[1]):
        window.addch(dimensions[0] - 2 - inputVertical, x, curses.ACS_HLINE)

    # Print input string
    window.addstr(dimensions[0] - 1 - inputVertical, 0, inputStr)

    # Write all changes to the window
    window.refresh()

# Send a raw string to the IRC server
def socksend(string):
    s.send(string+"\r\n")

# Get a single line from the IRC server
def getLine(): 
    tmp=s.recv(1)
    if not tmp: # connection closed
        return None
        
    while '\n' not in tmp:
        tmp += s.recv(1)
    tmp = tmp.rstrip('\r\n')
    return tmp

# Connect to IRC
def connect(port=6667):
    # set up socket things
    try:
        s.connect((v.server, port))
    except socket.error as serr:
        if serr.errno == errno.ECONNREFUSED:
            print v.server,'connection error: Connection refused'
        elif serr.errno == errno.ENOEXEC:
            print v.server,"connection error: Exec format error (maybe the server you specified doesn't exist?)"
        else:
            print v.server,'connection error:',errno.errcode[serr.errno]
        return False
    return True

# Display a help message. Not implemented yet
def showHelp():
    pass
    
# Interpret a line of user input.
def interpret(line):
    # Check for null string
    if line == '': return
    
    # if formatCommands = false, do no interpretation
    if not sett.formatCommands:
        socksend(line)
        return

    # this will be used frequently
    ccn = irclib.getCurrChannelName()

    # check to see if command or not
    # if not, default to sending a PRIVMSG to the current channel
    if line[0] != '/':
        if v.currChannel == 0:
            irclib.addCurrChannel(irclib.prn(['This is not a channel'],
                                             ['error']))
        else:
            socksend('PRIVMSG ' + ccn + ' :' + line)
            irclib.addCurrChannel(irclib.prn(['<',v.currNick,'> ',line],
                                             ['you','you','you','none']))
        return

    # if command, parse it
    # annoying thing here with the parsing, it would be nice to call
    # line.split() and use that, but if a person does /msg user "Hi  there"
    # or something, that needs to be preserved. 
    cmdlist = line.split(" ")
    noempty = line.split() # for space-independent commands
    command = cmdlist[0]
    tail=""
    if command == '/msg':
        tail = ' '.join(cmdlist[2:])
        if len(tail) == 0 or tail.isspace():
            irclib.addCurrChannel(irclib.prn(['Format: /msg user message'],
                                             ['error']))
            return
        socksend("PRIVMSG " + cmdlist[1] + " :" + tail)
        irclib.addCurrChannel(irclib.prn(['<'+v.currNick+'> ', tail],
                                         ['you', 'none']))
            
    elif command == '/me':
        # Format for /me commands wraps the message in ^A characters and
        # puts ACTION at the beginning (?)
        tail = ' '.join(cmdlist[1:])
        socksend('PRIVMSG ' + ccn + ' :' + chr(1) + 'ACTION ' + tail + chr(1))
        irclib.addCurrChannel(irclib.prn(['[', v.currNick, ' ' + tail + ']'],
                                         ['none', 'you', 'none']))
        
    elif command == '/join':
        if len(noempty) != 2:
            irclib.addCurrChannel(irclib.prn(['Format: /join channel'],
                                             ['error']))
            return
        socksend('JOIN '+noempty[1])

    elif command == '/part':
        if len(noempty) == 1:
            if v.currChannel == 0:
                irclib.addCurrChannel(irclib.prn(['This is not a channel'],
                                                 ['error']))
                return
            elif v.chanlist[v.currChannel].isQuery:
                irclib.eraseChannel(ccn)
                v.currChannel = 0
                return
            socksend('PART '+ccn)
        else:
            irclib.addCurrChannel(irclib.prn(['Format: /part'],
                                             ['error']))

    elif command == '/quit':
        tail = ' '.join(cmdlist[1:])
        finish('Program exited successfully', 0, tail)
        
    elif command == '/nick':
        if len(noempty) != 2:
            irclib.addCurrChannel(irclib.prn(['Format: /nick newnick'],
                                             ['error']))
            return
        socksend('NICK '+noempty[1])

    elif command == '/away':
        if len(noempty) == 1:
            socksend('AWAY')
        else:
            socksend('AWAY '+' '.join(cmdlist[1:]))

    elif command == '/help':
        showHelp()

    elif command == '/whois':
        if len(noempty) != 2:
            irclib.addCurrChannel(irclib.prn(['Format: /whois nick'],['error']))
            return
        socksend('WHOIS '+noempty[1])

    elif command == '/query':
        if len(noempty) != 2:
            irclib.addCurrChannel(irclib.prn(['Format: /query nick'],['error']))
            return
        new = irclib.insertChannel(noempty[1])
        v.currChannel = new

    elif command == '/mode':
        pass

    elif command == '/names':
        if len(noempty) == 1:
            socksend('NAMES '+irclib.getCurrChannelName())
        elif len(noempty) == 2:
            socksend('NAMES '+noempty[1])
        
    elif command == '/invite': # operator only command
        pass

    elif command == '/kick': # operator only command
        pass

    elif command == '/motd':
        pass

    elif command == '/op': # operator only command
        pass

    elif command == '/list':
        if len(noempty) > 2:
            irclib.addCurrChannel(irclib.prn(['Format: /list [channel]'],
                                             ['error']))
            return
        elif len(noempty) == 2:
            socksend('LIST '+noempty[1])
        socksend('LIST')

    elif command == '/ping':
        pass

    elif command == '/admin':
        socksend('ADMIN')

# Formats a nickname
def fmtNick(nick):
    return "<"+nick+">"

# Cleans up and closes the program
def finish(mess="", code=0, quitmsg=''):
    socksend('QUIT :Quit')
    s.close()
    curses.endwin()
    if mess != "": print mess
    sys.exit(code)

# for signal handler
def signalHandler(signal, frame):
    finish()
    
# begin program execution
#
# ONLY CLASSES AND FUNCTIONS AND VARIABLES BEFORE THIS
#

# initial default values for stuff
attemptIdent = 'x'
attemptRealname = 'x'
attemptPassword = ''
attemptChannel = ''
attemptPort = 6667

# usage: [name] server nick [[--channel=<channel>] [--port=<port>] [--realname=<realname>] [--ident=<ident>] [--password=<password>]]
if len(sys.argv) < 3:
    print 'Usage: '+sys.argv[0]+' server nick [options]'
    print '  options: --channel= --realname= --ident= --password='
    print '           --raw-output'
    print '           --show-server-stats'
    print '           --show-motd'
    print '           --disregard-nothing'
    print '           --raw-commands'
    print '           --hide-pings'
    print '           --show-nonstandard'
    sys.exit(1)

v.server = sys.argv[1]
attemptNick = sys.argv[2]
for x in range(3, len(sys.argv)):
    st = sys.argv[x]
    if st[:9] == '--channel':
        attemptChannel = st[10:]
    elif st[:6] == '--port':
        attemptPort = st[7:]
        if not attemptPort.isdigit():
            print '--port argument must be a number'
            sys.exit(1)
        attemptPort = int(attemptPort)
    elif st[:10] == '--realname':
        attemptRealname = st[11:]
    elif st[:7] == '--ident':
        attemptIdent = st[8:]
    elif st[:10] == '--password':
        attemptPassword = st[11:]
    elif st == '--raw-output':
        sett.formatOutput = False
    elif st == '--show-server-stats':
        sett.hideServerStats = False
    elif st == '--show-motd':
        sett.hideMOTD = False
    elif st == '--disregard-nothing':
        sett.disregard = False
    elif st == '--raw-commands':
        sett.formatCommands = False
    elif st == '--no-pings':
        sett.showPings = False
    elif st == '--show-nonstandard':
        sett.ignoreNonstandard = False
    else:
        print 'Unrecognized option '+st
        sys.exit(1)

# try to connect
sock = connect(attemptPort)
if sock == False:
    print "Failed to connect"
    sys.exit(1)

# add 'default' (non-channel) channel and set current channel to that
v.chanlist.append(irclib.chan('server'))
#var.currChannel = 0

# set up ctrl-c signal handler
# this should go right before curses starts
signal.signal(signal.SIGINT, signalHandler)

# set up curses
window = curses.initscr()
curses.start_color()
curses.init_pair(1, curses.COLOR_BLACK, curses.COLOR_WHITE) # header bar
curses.init_pair(2, curses.COLOR_GREEN, curses.COLOR_BLACK) # nick
curses.init_pair(3, curses.COLOR_CYAN, curses.COLOR_BLACK) # you
curses.init_pair(4, curses.COLOR_RED, curses.COLOR_BLACK) # notices
curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK) # old channel
curses.init_pair(6, curses.COLOR_BLACK, curses.COLOR_CYAN) # you in header
curses.init_pair(7, curses.COLOR_BLACK, curses.COLOR_YELLOW) # channel in header
curses.init_pair(8, curses.COLOR_MAGENTA, curses.COLOR_BLACK) # error
curses.init_pair(9, curses.COLOR_BLACK, curses.COLOR_RED) # notification
curses.init_pair(10, curses.COLOR_BLUE, curses.COLOR_BLACK) # time
curses.noecho()
window.keypad(1)

# map strings to their associated styles
stylemap = {
    'none': curses.color_pair(0),
    'header': curses.color_pair(1),
    'nick': curses.color_pair(2),
    'you': curses.color_pair(3) | curses.A_BOLD,
    'notice': curses.color_pair(4),
    'channel': curses.color_pair(4),
    'youHeader': curses.color_pair(6),
    'channelHeader': curses.color_pair(7),
    'error': curses.color_pair(8),
    'notification': curses.color_pair(9),
    'time': curses.color_pair(10)
}

# draw the window for the first time
redraw()

# send in user info
socksend("USER "+attemptIdent+" "+v.server+" "+v.server+" "+attemptRealname)
if attemptPassword != '': socksend("PASS "+attemptPassword)
socksend("NICK "+attemptNick)

# wait for a 001 success message from the server
while 1:
    line = getLine()
    
    if line is None:
        finish("Could not finish connecting to the server.", 1)
            
    results = irclib.parse(line)
    if results.command == "001":
        # hooray, success!
        v.currNick = results.params[0]
        irclib.addNumChannel(0, irclib.prn([results.trail], ['notice']))
        redraw()
        break
    if results.command == "433":
        # nickname in use, generate a random temporary nickname
        msg = irclib.prn([attemptNick, ' is already in use - enter new nick'],
                         ['nick', 'error'])
        irclib.addNumChannel(0, msg)
        redraw()
        newnick = window.getstr(dimensions[0]-1, 0)
        socksend('NICK '+newnick)
        continue

    irclib.process(line);
    redraw()
    
if attemptChannel != '': socksend('JOIN '+attemptChannel)
    
sock_list = [sys.stdin, s]
while True:
    # Listen for input from the socket and from stdin
    read_socks, write_socks, err_socks = select.select(sock_list, [], [])
    for sock in read_socks:
        if sock == s:
            try:
                data = getLine()
            except socket.error as serr:
                if serr.errno == errno.ECONNRESET:
                    finish("Connection closed.", 1)
                raise serr

            if data[:4] == "PING":
                socksend('PONG :Pong')
                if sett.showPings:
                    irclib.addNumChannel(0, irclib.prn(['PING'],['notice']))
                    redraw()
                continue
            irclib.process(data)
            redraw()
            
        else:
            inputVertical = len(inputStr) // dimensions[1]
            char = window.getch(dimensions[0]-1, len(inputStr) % dimensions[1])
            time.sleep(.001)
            if char == 127: # backspace
                inputStr = inputStr[:-1]
                
            elif char == 9: # tab
                scrollPos = 0
                v.currChannel += 1
                if v.currChannel >= len(v.chanlist):
                    v.currChannel = 0

            elif char == curses.KEY_UP: # up arrow
                if scrollPos < len(v.chanlist[v.currChannel].msgs) - 1:
                    scrollPos += 1

            elif char == curses.KEY_DOWN: # down arrow
                if scrollPos > 0: scrollPos -= 1

            elif char == curses.KEY_RIGHT: # right arrow
                scrollPos = 0
                
            elif char == ord('\n'):
                interpret(inputStr)
                inputStr = ''
            else:
                inputStr += chr(char)
            
            redraw()
    
