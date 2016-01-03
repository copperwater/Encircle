# Values which should, ideally, be user-controlled options.
# When adding new settings, name them such that:
# 1) If it is a boolean option, its default (and value here) should be True.

# whether the server output gets formatted
formatOutput = True

# whether the client should parse user input before send
formatCommands = True

# whether a bunch of server statistics get ignored (filter)
hideServerStats = True
 
# whether the motd gets hidden (filter)
hideMOTD = True

# whether some superfluous server commands get ignored
hideBeginsEnds = True

# whether pings should be logged
showPings = True

# whether to print the time a message was received
showTime = False

# whether nonstandard messages will be ignored
ignoreNonstandard = True

# time that messages will be kept in the queue, in seconds, after which they
# will be deleted
msgTimeout = 86400

# file to log to, a value of '' does no logging
# UNIMPLEMENTED
#logFile = '' 

