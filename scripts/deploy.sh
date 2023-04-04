#!/usr/bin/env bash

# The http server not support data-form or x-www-url-encoded-form,
# so the archive file must just in the post body, so use --data-binary
# as curl argument.
#
# $1 is the archive path to be sent to http server
# $2 is the http server (including schema, host, port and path)
#
# Example:
#   curl --data-binary @public.tar.gz http://localhost:8080/

if (( $# != 2 )) ; then
    echo "parameter not meet"
    exit 1
fi

curl --data-binary @"$1" "$2"
