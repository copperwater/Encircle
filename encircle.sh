#!/bin/sh

# get python version
pyver=`python -c 'import sys; print(sys.version_info[0])'`

# if python isn't installed or is not version 2, this can't run
if [ ! $? -eq 0 ]; then
    echo "You don't appear to have Python installed."
    exit 1
elif [[ $pyver != 2 ]]; then
    echo "Your default Python version is 3; this cannot run on Python 3."
    exit 1
fi

# run with all arguments passed to this script
python encircleClient.py $@
