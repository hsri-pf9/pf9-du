#!/usr/bin/env bash

# Copyright (c) 2017 Platform9 Systems Inc.

THIS_DIR=$(cd $(dirname ${BASH_SOURCE[0]}); pwd)

function download_nocert() {
    if [ -z "$1" ]; then
        echo "download_nocert(): arg1: rpm or deb" >&2
        return 1
    elif [ -z "$2" ]; then
        echo "download_nocert(): arg2: keystone token" >&2
        return 1
    fi

    local packagelist="${THIS_DIR}/packagelist"

    echo "Getting package list..."
    curl -# ${CURL_INSECURE} -f -H "X-Auth-Token: $2" "https://$DU_FQDN/private/nocert-packagelist.$1" > ${packagelist}
    if [ ! -f "${packagelist}" ]; then
        echo "Failed to download package list, exiting." >&2
        return 1
    fi

    while read f; do
        echo "Getting ${f}..."
        curl -# ${CURL_INSECURE} -f -H "X-Auth-Token: $2" -o ${THIS_DIR}/${f} --create-dirs "https://${DU_FQDN}/private/${f}"
        if [ ! -f "${THIS_DIR}/${f}" ]; then
            echo "Failed to download ${f} exiting." >&2
            return 1
        fi
    done < ${packagelist}
    return 0
}

function packages_present() {
    if [ -z "$1" ]; then
        echo "packages_present(): please specify rpm or deb" >&2
        return 1
    fi
    for g in pf9-hostagent*.$1 pf9-comms*.$1; do
        if ! stat -t "${THIS_DIR}/$g" >/dev/null 2>&1; then
            return 2
        fi
    done
}

function update_config() {
    if [ -d "${THIS_DIR}/etc/pf9" ]; then
        echo "Updating host certificates and configuration..."
        chown -R pf9:pf9group ${THIS_DIR}/etc/pf9
        chmod --quiet 400 /etc/pf9/certs/hostagent/key.pem || true
        cp -rfvpb -S'.bak' "${THIS_DIR}/etc/pf9" /etc/
    else
        echo "No configuration found, no updates."
    fi
}
