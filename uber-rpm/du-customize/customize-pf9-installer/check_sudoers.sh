#!/bin/bash
# Copyright (c) 2015 Platform9 Systems Inc.

function check_sudoers()
{
    echo "Checking sudoers configuration"
    if ! grep -Eq "^[#,@]includedir[[:blank:]]+/etc/sudoers.d" /etc/sudoers; then
        echo "The sudoers file does not have the #includedir directive for /etc/sudoers.d"
        exit ${CORRUPT_SUDOERS_FILE}
    fi
}
