#!/bin/bash
#
# Run all customization scripts in /opt/pf9/pf9-du/ directory on a DU
# host (where this script itself will also be installed) one by one,
# following their naming order.
#
# A customization script must start with two digits, and be executable.
# It can be written in any language. Preferably the script should be
# named without extension following conventions in /etc/rc.d/rcX.d.
# For example, customization script for component "foo" should be named
# "20foo" as opposed to "20foo.sh" or "20foo.py".
#
# If any customization script fails, the DU customization process aborts
# immediately. For details, see
#
# https://platform9.atlassian.net/wiki/display/eng/Deployment
#

set -e

# Dump environment variables for debugging purpose
env | sort

cd $(dirname $0)

for i in [0-9][0-9]*; do
    if test -x $i; then
        echo "[Running $i]"
        ./$i
    fi
done
