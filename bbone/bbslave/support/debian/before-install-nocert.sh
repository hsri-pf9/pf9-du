#!/bin/bash
set -e

HOSTAGENT_CNF=/etc/pf9/hostagent.conf
HOSTAGENT_DPKG_CNF=/var/lib/dpkg/info/pf9-hostagent.conffiles
CURL_OPTS_CHECK=" -o /dev/null --head --write-out %{http_code}"
CURL_OPTS="--retry 5 --silent"
HOSTAGENT_CNF_URL="http://localhost:9080/private/hostagent.conf"
CERTS_DIR="/etc/pf9/certs"

if [[ "$1" = "upgrade" ]]; then
    if [ ! -f ${HOSTAGENT_DPKG_CNF} ] || ! grep ${HOSTAGENT_CNF} ${HOSTAGENT_DPKG_CNF} > /dev/null ; then
        # dpkg pf9-hostagent.conffiles doesn't exist or hostagent.conf is not present in conffiles
        mv ${HOSTAGENT_CNF} ${HOSTAGENT_CNF}.$(date +"%Y-%m-%d-%H-%M").bkup
    fi
    # Download the latest hostagent.conf from the DDU.
    if [[ $(curl ${CURL_OPTS} ${CURL_OPTS_CHECK} ${HOSTAGENT_CNF_URL}) == 200 ]]; then
        echo "Downloading hostagent.conf from PF9"
        if ! curl ${CURL_OPTS} --fail -o ${HOSTAGENT_CNF}.from.du ${HOSTAGENT_CNF_URL}; then
            # Failed to download the hostagent.conf from DDU
            echo "Failed to download hostagent.conf from PF9"
            exit 1
        fi
    else
        echo "Failed to check existence hostagent.conf from PF9"
        exit 1
    fi
    # Backup the certs directory
    if [[ -d ${CERTS_DIR} ]]; then
        echo "Creating a backup of certs directory"
        rm -rf ${CERTS_DIR}.bkup
        cp -r ${CERTS_DIR} ${CERTS_DIR}.bkup
    fi
fi
