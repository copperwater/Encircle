#!/usr/bin/env python

import curses
import sys
import encircleLib as elib
import socket
import select
import signal
import encircleSettings as settings
import encircleVars as variables
import time
import errno
import os # may be moved if read conf stuff gets moved

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
    window.addstr(0, 0, variables.server, stylemap['header'])
    currlen = len(variables.server)
    window.addstr(0, currlen, ' - ', stylemap['header'])
    currlen += 3
    # Current channel/query
    chanName = variables.chanlist[variables.currChannel].name
    window.addstr(0, currlen, ' '+chanName+' ',stylemap['channelHeader'])
    currlen += len(chanName)+2
    window.addstr(0, currlen, ' - ', stylemap['header'])
    # Current nick
    if variables.currNick != '':
        currlen += 3
        window.addstr(0, currlen, ' '+variables.currNick+' ', stylemap['youHeader'])
    # Unread message alert
    anyUnread = False
    for x in range(0, len(variables.chanlist)):
        if variables.currChannel == x:
            variables.chanlist[x].hasUnread = False
        elif variables.chanlist[x].hasUnread:
            anyUnread = True
    if anyUnread:
        window.addstr(0, dimensions[1]-4, ' ! ', stylemap['notification'])


    # Calculate the number of lines in the user input line
    inputVertical = len(inputStr) // dimensions[1]
        
    # Print strings backwards from bottom line
    chanList = variables.chanlist[variables.currChannel].msgs
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
        if settings.showTime:
            window.addstr('['+time.strftime('%H:%M',
                                            time.localtime(prn.tstamp))+'] ',
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
    print variables.server
    # set up socket things
    try:
        s.connect((variables.server, port))
    except socket.error as serr:
        if serr.errno == errno.ECONNREFUSED:
            print variables.server,'connection error: Connection refused'
        elif serr.errno == errno.ENOEXEC:
            print variables.server,"connection error: Exec format error (maybe the server you specified doesn't exist, or you have a problem connecting to the Internet)"
        else:
            print variables.server,'connection error:',errno.errcode[serr.errno]
        return False
    return True

# Display a help message. Not implemented yet
def showHelp():
    pass
    
# Interpret a line of user input.
# I am only implementing commands described in RFCs 1459 and 2812.
# freenode has a lot of nonstandard ones.
def interpret(line):
    # Check for null string
    if line == '': return
    
    # if formatCommands = false, do no interpretation
    if not settings.formatCommands:
        # check for /option being used, which should switch back to normal
        # commands
        if line.split()[0] == '/option':
            settings.formatCommands = True
            return
        socksend(line)
        return

    # this will be used frequently
    ccn = elib.getCurrChannelName()

    # check to see if command or not
    # if not, default to sending a PRIVMSG to the current channel
    if line[0] != '/':
        if variables.currChannel == 0:
            elib.addCurrChannel(elib.prn(['You are not on a channel'],
                                             ['error']))
        else:
            socksend('PRIVMSG ' + ccn + ' :' + line)
            elib.addCurrChannel(elib.prn(['<',variables.currNick,'> ',line],
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
            elib.addCurrChannel(elib.prn(['Format: /msg user message'],
                                             ['error']))
            return
        socksend("PRIVMSG " + cmdlist[1] + " :" + tail)
        # This creates a new private window like a query
        new = elib.insertChannel(cmdlist[1], True)
        variables.currChannel = new
        elib.addNumChannel(new, elib.prn(['<'+variables.currNick+'> ', tail],
                                             ['you', 'none']))
        
    elif command == '/me':
        # Format for /me commands wraps the message in ^A characters and
        # puts ACTION at the beginning (?)
        tail = ' '.join(cmdlist[1:])
        socksend('PRIVMSG ' + ccn + ' :' + chr(1) + 'ACTION ' + tail + chr(1))
        elib.addCurrChannel(elib.prn(['[', variables.currNick, ' ' + tail + ']'],
                                         ['none', 'you', 'none']))
        
    elif command == '/join':
        if len(noempty) != 2:
            elib.addCurrChannel(elib.prn(['Format: /join channel'],
                                             ['error']))
            return
        socksend('JOIN '+noempty[1])

    elif command == '/part':
                              
        if len(noempty) == 1:
            if variables.currChannel == 0:
                elib.addCurrChannel(elib.prn(['This is not a channel'],
                                                 ['error']))
                return
            elif variables.chanlist[variables.currChannel].isQuery:
                elib.eraseChannel(ccn)
                variables.currChannel = 0
                return
            socksend('PART '+ccn)
        else:
            elib.addCurrChannel(elib.prn(['Format: /part'],
                                             ['error']))

    elif command == '/quit':
        tail = ' '.join(cmdlist[1:])
        finish('', 0, tail)
        
    elif command == '/nick':
        if len(noempty) != 2:
            elib.addCurrChannel(elib.prn(['Format: /nick newnick'],
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
            elib.addCurrChannel(elib.prn(['Format: /whois nick'],['error']))
            return
        socksend('WHOIS '+noempty[1])

    elif command == '/query':
        if len(noempty) != 2:
            elib.addCurrChannel(elib.prn(['Format: /query nick'],['error']))
            return
        new = elib.insertChannel(noempty[1], True)
        variables.currChannel = new

    elif command == '/option':
        if len(noempty) < 2:
            elib.addCurrChannel(elib.prn(['Format: /option arg1 [arg2...]'],
                                             ['error']))
            return
            
        if noempty[1] == 'pings':
            if len(noempty) == 2:
                settings.showPings = not settings.showPings
            else:
                if noempty[2] == 'on':
                    settings.showPings = True
                elif noempty[2] == 'off':
                    settings.showPings == False

        if noempty[1] == 'format-output':
            if len(noempty) == 3:
                if noempty[2] == 'on':
                    settings.formatOutput = True
                elif noempty[2] == 'off':
                    settings.formatOutput = False

        if noempty[1] == 'format-commands':
            if len(noempty) == 3:
                if noempty[2] == 'on':
                    settings.formatCommands = True
                elif noempty[2] == 'off':
                    settings.formatCommands = False
                    

        if noempty[1] == 'nonstandard':
            if len(noempty) == 3:
                if noempty[2] == 'on':
                    settings.ignoreNonstandard = False
                elif noempty[2] == 'off':
                    settings.ignoreNonstandard = True

        if noempty[1] == 'time':
            settings.showTime = not settings.showTime
            redraw()
            
    elif command == '/mode':
        if len(noempty) < 3:
            elib.addCurrChannel(elib.prn([
                'Format: /mode channel (+/-)modes [parameters]', '\n',
                'Run /help mode for more information on modes and parameters.'],
                                             ['error','error','error']))

    elif command == '/names':
        if len(noempty) == 1:
            socksend('NAMES '+elib.getCurrChannelName())
        elif len(noempty) == 2:
            socksend('NAMES '+noempty[1])
        
    elif command == '/invite': # operator only command
        pass

    elif command == '/kick': # operator only command
        pass

    elif command == '/notice':
        if len(cmdlist) < 3:
            elib.addCurrChannel(elib.prn(['Format: /notice target message'],
                                             ['error']))
        tail = ' '.join(cmdlist[2:])
        socksend('NOTICE '+cmdlist[1]+' :'+tail)

    elif command == '/motd':
        pass

    elif command == '/op': # operator only command
        pass

    elif command == '/list':
        if len(noempty) > 2:
            elib.addCurrChannel(elib.prn(['Format: /list [channel]'],
                                             ['error']))
            return
        elif len(noempty) == 2:
            socksend('LIST '+noempty[1])
        socksend('LIST')

    elif command == '/ragequit': # kind of a joke but here it is
        finish('', 0, 'RAGEQUIT')
        
    elif command == '/ping':
        pass

    elif command == '/admin':
        socksend('ADMIN')

    elif command == '/interpret':
        settings.formatCommands = not settings.formatCommands

    else:
        elib.addCurrChannel(elib.prn(['Unrecognized command ', command],
                                         ['error', 'error']))

# Formats a nickname
def fmtNick(nick):
    return "<"+nick+">"

# Cleans up and closes the program
def finish(mess="", code=0, quitmsg='Quit'):
    socksend('QUIT :'+quitmsg)
    #s.close()
    curses.endwin()
    if mess != "": print mess
    sys.exit(code)

# for signal handler
def signalHandler(signal, frame):
    finish()

    '''
    # conf file read and set settings
attemptServer=''
attemptNick=''
    
def readConfFile(filename=os.path.expanduser("~/.irc_conf")):
    ctr=1
    with open(filename, "r") as f:
        for line in f.readlines():
            if len(line) == 0 or line[0] == "#" or line.isspace():
                pass
            elif line[:14] == 'defaultserver=':
                attemptServer=line[14:]
            elif line[:12] == 'defaultnick=':
                attemptNick=line[12:]
            else:
                print 'Warning: line', ctr, "of config file is invalid"

            ctr += 1 

readConfFile()
sys.exit(0)
    '''

# begin program execution
#
# ONLY CLASSES AND FUNCTIONS AND VARIABLES BEFORE THIS
#

# stop creating .pyc files
sys.dont_write_bytecode = True

# initial default values for stuff
attemptIdent = 'x'
attemptRealname = 'x'
attemptPassword = ''
attemptChannel = ''
attemptPort = 6667

# read prefs from ~/.irc_conf here


# usage: [name] server nick [[--channel=<channel>] [--port=<port>] [--realname=<realname>] [--ident=<ident>] [--password=<password>]]
if len(sys.argv) < 3:
    print 'Usage: encircle server nick [options]'
    print '  options: --channel= --realname= --ident= --password='
    print '           --raw-output'
    print '           --show-server-stats'
    print '           --show-motd'
    print '           --show-begins-and-ends'
    print '           --raw-commands'
    print '           --hide-pings'
    print '           --show-nonstandard'
    print '           --show-time'
    sys.exit(1)

variables.server = sys.argv[1]
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
        settings.formatOutput = False
    elif st == '--show-server-stats':
        settings.hideServerStats = False
    elif st == '--show-motd':
        settings.hideMOTD = False
    elif st == '--show-begins-and-ends':
        settings.hideBeginsEnds = False
    elif st == '--raw-commands':
        settings.formatCommands = False
    elif st == '--no-pings':
        settings.showPings = False
    elif st == '--show-nonstandard':
        settings.ignoreNonstandard = False
    elif st == '--show-time':
        settings.showTime = True
    else:
        print 'Unrecognized option '+st
        sys.exit(1)

# try to connect
sock = connect(attemptPort)
if sock == False:
    print "Failed to connect"
    sys.exit(1)

# add 'default' (non-channel) channel and set current channel to that
variables.chanlist.append(elib.chan('server'))
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
curses.init_pair(5, curses.COLOR_YELLOW, curses.COLOR_BLACK) # used to be the channel color
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
socksend("USER "+attemptIdent+" "+variables.server+" "+variables.server+" "+attemptRealname)
if attemptPassword != '': socksend("PASS "+attemptPassword)
socksend("NICK "+attemptNick)

# wait for a 001 success message from the server
while 1:
    line = getLine()
    
    if line is None:
        finish("Could not finish connecting to the server.", 1)
            
    results = elib.parse(line)
    if results.command == "001":
        # hooray, success!
        variables.currNick = results.params[0]
        elib.addNumChannel(0, elib.prn([results.trail], ['notice']))
        redraw()
        break
    if results.command == "433":
        # nickname in use, generate a random temporary nickname
        msg = elib.prn([attemptNick, ' is already in use - enter new nick'],
                         ['nick', 'error'])
        elib.addNumChannel(0, msg)
        redraw()
        newnick = window.getstr(dimensions[0]-1, 0)
        socksend('NICK '+newnick)
        continue

    elib.process(line);
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
                    finish("Connection closed.", 1, 'Connection closed')
                raise serr

            if data is None:
                finish('Connection terminated', 1, 'Connection terminated')
        
            elif data[:4] == "PING":
                socksend('PONG :Pong')
                if settings.showPings:
                    elib.addNumChannel(0, elib.prn(['PING at '+time.strftime('%H:%M:%S')],['notice']))
                    redraw()
                continue
                
            elif data[:5] == 'ERROR':
                # something very bad is happening
                elib.addCurrChannel(elib.prn([data],['error']))
                
            else:
                elib.process(data)
                
            redraw()
            
        else:
            inputVertical = len(inputStr) // dimensions[1]
            char = window.getch(dimensions[0]-1, len(inputStr) % dimensions[1])
            time.sleep(.001)
            if char == curses.KEY_BACKSPACE or char == 127: # backspace
                inputStr = inputStr[:-1] # [:-1] sad blockhead
                
            elif char == 9: # tab
                scrollPos = 0
                variables.currChannel += 1
                if variables.currChannel >= len(variables.chanlist):
                    variables.currChannel = 0

            elif char == curses.KEY_UP: # up arrow
                if scrollPos < len(variables.chanlist[variables.currChannel].msgs) - 1:
                    scrollPos += 1

            elif char == curses.KEY_DOWN: # down arrow
                if scrollPos > 0: scrollPos -= 1

            elif char == curses.KEY_RIGHT: # right arrow
                scrollPos = 0

            elif char == curses.KEY_LEFT: # left arrow
                pass # does nothing
                
            elif char == ord('\n'):
                interpret(inputStr)
                inputStr = ''
            elif char > 255:
                pass # some weird keys like F1-F12 that crash chr()
            else:
                inputStr += chr(char)
            
            redraw()
    
