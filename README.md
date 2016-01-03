A simple IRC client written in Python. It runs in a terminal and uses the curses library to make a display.

It works with ordinary IRC client syntax, and it also provides low-level access to receive and send raw data to the server.

Features of note:
* Channels and queries are all given their own screens. Use TAB to switch between windows.
* Scrolling through a window is done with the arrow keys.

Arguments/initialization options:
* --port=_port_ attempts to connect to the server on the given port (the default is 6667)
* --channel=_chan_ immediately sends a /join command to the specified channel upon connecting
* --realname=_name_ and --ident=_ident_ set your real name and ident (they will both otherwise be 'x' because they cannot be blank)
* --password=_pass_ sends a password (use if your nickname is registered; also note that this uses the IRC PASS command and some servers require you to send a message to NickServ instead. Currently Encircle supports only PASS.)
There are more than these, but they mostly deal with setting some behavior of the program to a non-default value. Consult the extended documentation to see more about them.

This client was tested primarily on irc.freenode.net and a few other servers.
