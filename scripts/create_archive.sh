#!/usr/bin/env bash

# Create an archive named with "$2", containing all files under "$1"
# and no subdir containing all others

if (( $# != 2 )) ; then
    echo "parameters not meet"
    exit 1
fi

find "$1" -mindepth 1 -not -type d -printf "%P\n" | tar -C "$1" -cf "$2" --gzip -T -
