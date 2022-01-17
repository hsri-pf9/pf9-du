#!/bin/bash
set -e

HOSTAGENT_CNF=/etc/pf9/hostagent.conf
HOSTAGENT_DPKG_CNF=/var/lib/dpkg/info/pf9-hostagent.conffiles

if [[ "$1" = "upgrade" ]]; then
    if [ ! -f ${HOSTAGENT_DPKG_CNF} ] || ! grep ${HOSTAGENT_CNF} ${HOSTAGENT_DPKG_CNF} > /dev/null ; then
        # dpkg pf9-hostagent.conffiles doesn't exist or hostagent.conf is not present in conffiles
        mv ${HOSTAGENT_CNF} ${HOSTAGENT_CNF}.$(date +"%Y-%m-%d-%H-%M").bkup
    fi
fi
