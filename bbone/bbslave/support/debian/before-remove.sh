#!/bin/bash
set -e

# Arguments to the prerm script:
#script_name=$0
script_step=$1
new_version=$2


if [ "$script_step" = "remove" ]; then
    systemctl stop pf9-hostagent > /dev/null 2>&1
    systemctl disable pf9-hostagent > /dev/null 2>&1
    rm /lib/systemd/system/pf9-hostagent.service && systemctl daemon-reload
    LINKED_FILES="apt_inst.so  apt_pkg.so"
    for ln_file in $LINKED_FILES
    do
        if [[ -L /opt/pf9/python/lib/python2.7/$ln_file ]]; then
            rm /opt/pf9/python/lib/python2.7/$ln_file
        fi
    done
fi
