# Global variables used by both the client and IRC library

# I am not expecting this client to be able to connect to multiple servers
# at once. Most clients can't.

# server this is connected to
server = ""

# nick on the server
currNick = ""

# current index in the channel list (active channel)
currChannel = 0

# list of all channels. 0 is the "server" window and is not a channel, and this list may also include queries for direct messaging.
chanlist = []
