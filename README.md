A simple IRC client written in Python. It runs in a terminal and uses the curses library as a display.

It works with ordinary IRC client syntax, and it also provides low-level access to receive and send raw data to the server.

Features of note:
* Channels and queries are all given their own screens. The currently displaying one can be changed with TAB.
* Scrolling through a window is done with the arrow keys.

Arguments/initialization options:
* --channel=_chan_ immediately sends a /join command to the specified channel upon connecting
* --realname=_name_ and --ident=_ident_ set your real name and ident (they will both otherwise be 'x')
* --password=_pass_ sends a password if your nickname is registered
* --raw-output disables all formatting of the output
* --raw-commands disables all parsing of your input
* --disregard-nothing forces the program to show certain messages that would otherwise be suppressed, such as "End of /NAMES list".
* --show-server-stats prints some server statistics that would otherwise be ignored, such as the server creation time and number of users
* --show-motd will print the message of the day, which would otherwise be suppressed.
* --hide-pings will stop server pings from appearing
* --show-nonstandard enables nonstandard (non-RFC) commands to be processed. If they are enabled and the server sends a nonstandard an unexpected format, the program may crash. 

This client was tested primarily on irc.freenode.net.
