#!/bin/bash

# Show the status from the proc folder
svcname="pf9-hostagent"
pid=`cat /var/run/$svcname.pid`

digits_re="[0-9]+"
if [[ "$pid" =~ $digits_re ]] && [ -d "/proc/$pid" ] && [ -f /proc/$pid/status ]; then
    ( set -x && cat /proc/$pid/status )
else
    echo "Could not find proc status using PID: $pid" 1>&2
fi

set -x

service --status-all
ps aux | grep pf9

