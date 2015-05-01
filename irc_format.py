class pcol:
    end = '\033[0m'
    modebold = '\033[1m'
    modeunder = '\033[4m'
    modeblink = '\033[5m'
    fgblack = '\033[30m'
    fgred = '\033[31m'
    fggreen = '\033[32m'
    fgyellow = '\033[33m'
    fgblue = '\033[34m'
    fgmagenta = '\033[35m'
    fgcyan = '\033[36m'
    fgwhite = '\033[37m'
    bgblack = '\033[40m'
    bgred = '\033[41m'
    bggreen = '\033[42m'
    bgyellow = '\033[43m'
    bgblue = '\033[44m'
    bgmagenta = '\033[45m'
    bgcyan = '\033[46m'
    bgwhite = '\033[47m'
    
def unick(u=None): #Styles an instance of the user's nickname.
    return pcol.fgcyan + pcol.modebold + (NICK if u == None else u)  + pcol.end

def onick(o): #Styles an instance of someone else's nickname.
    return pcol.fgyellow + o + pcol.end

def important(ln): #Styles an "important" line and highlights occurences of the user's name.
    tmp = ln.replace(NICK, pcol.fgcyan+NICK+pcol.end)
    tmp = tmp.replace(pcol.end, pcol.end+pcol.modebold)
    return pcol.modebold+tmp+pcol.end

def system(ln): #Styles a non-chat message
    tmp = ln.replace(pcol.end, pcol.end+pcol.fgred)
    return pcol.fgred+tmp+pcol.end

def privm(ln): #Styles a private message
    st = pcol.fggreen+pcol.modebold
    tmp = ln.replace(pcol.end, pcol.end+st)
    return st+tmp+pcol.end

from datetime import datetime
def gettimestr():
    return str(datetime.now().hour).zfill(2)+":"+str(datetime.now().minute).zfill(2)
