#!/bin/bash
set -e

# Arguments to the prerm script:
#script_name=$0
script_step=$1
new_version=$2


if [ "$script_step" = "remove" ]; then
    . /opt/pf9/pf9-service-functions.sh
    pf9_service_stop pf9-hostagent > /dev/null 2>&1
    if is_ubuntu_14; then
        pf9_remove_service_files pf9-hostagent
        pf9_disable_service_on_boot pf9-hostagent > /dev/null 2>&1
    fi

    if is_ubuntu_16; then
        pf9_disable_service_on_boot pf9-hostagent > /dev/null 2>&1
        pf9_remove_service_files pf9-hostagent
        LINKED_FILES="apt_inst.so  apt_pkg.so"
        for ln_file in $LINKED_FILES
        do
            if [[ -L /opt/pf9/python/lib/python2.7/$ln_file ]]; then
                rm /opt/pf9/python/lib/python2.7/$ln_file
            fi
        done
    fi
fi
