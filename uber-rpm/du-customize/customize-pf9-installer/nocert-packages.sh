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
    local CURL_RETRY_OPTS="--retry 5" # without a retry delay the exponential backoff algo will kick in

    echo "Getting package list..."
    curl -# ${CURL_RETRY_OPTS} ${CURL_INSECURE} -f -H "X-Auth-Token: $2" "https://$DU_FQDN/protected/nocert-packagelist.$1" > ${packagelist}
    if [ ! -f "${packagelist}" ]; then
        echo "Failed to download package list, exiting." >&2
        return 1
    fi

    while read f; do
        echo "Getting ${f}..."
        if ! curl ${CURL_RETRY_OPTS} ${CURL_INSECURE} -f -H "X-Auth-Token: $2" -o ${THIS_DIR}/${f} --create-dirs "https://${DU_FQDN}/protected/${f}" ; then
            if [ -n "${INF_790_WEBHOOK}" ]; then
                msg="$(hostname) with DU ${DU_FQDN} failed to download ${f}"
                echo ${msg}
                curl ${CURL_RETRY_OPTS} -d "{\"text\":\"$msg\"}" "${INF_790_WEBHOOK}"
                return 1
            fi
        fi
        if [ ! -f "${THIS_DIR}/${f}" ]; then
            echo "Failed to download ${f} exiting." >&2
            return 1
        fi
        # The following two echo's succeed even if awk/md5sum are absent -- ok
        echo "file size: $(ls -l ${THIS_DIR}/${f} | awk '{print $5}')"
        echo "file md5 checksum: $(md5sum ${THIS_DIR}/${f})"
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

function get_certs_from_vouch() {
    if [ -z "$1" ]; then
        echo "get_certs_from_vouch(): arg1: keystone token" >&2
        return 1
    fi
    if [ -z "$2" ]; then
        echo "get_certs_from_vouch(): arg2: host_id" >&2
    fi

    echo 'Checking for per-host certificate signing...'
    local host_certs=/opt/pf9/hostagent/bin/host-certs
    local return_code=0
    local vouch_args="--vouch-url https://${DU_FQDN}/vouch --keystone-token $1"
    if $host_certs can-sign ${vouch_args}; then
        local hostname=$(hostname) || true
        if [ -n "${hostname}" ]; then
            # Get first 54 chars of hostname
            adj_host_name=$(echo ${hostname} | cut -c 1-54)
            # Append the - to hostname to tack on the uuid later
            adj_host_name=${adj_host_name}-
        fi
        # Get first 8 chars of host uuid
        local short_host_uuid=$(echo $2 | cut -c 1-8)
        # CN = adjusted hostname + first 8 chars of uuid
        common_name=${adj_host_name}${short_host_uuid}

        # Best attempt to implement hostname regex as per RFC https://tools.ietf.org/html/rfc1123
        # More consumable writeup here https://en.wikipedia.org/wiki/Hostname#Syntax
        # Below regex tries to ensure alphanumeric start and end of the CN,
        # with alphanumeric, - characters between . separated strings.
        # Note that it doesn't impose length restrictions on the strings.
        # Valid CN: host1, host1.example.com, host-1.example-1.com
        # Invalid CN: -host1, host1.example.com-, host1.example!
        valid_cn_regex='^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$'
        if ! $(echo ${common_name} | grep -P ${valid_cn_regex} > /dev/null); then
            echo "WARNING: ${common_name} doesn't appear to meet the CN requirements for the CSR. Proceeding anyway but the signing request may fail."
        fi
        echo "Using certificate common name = ${common_name}."
        $host_certs refresh ${vouch_args} --common-name ${common_name} || return_code=$?
    else
        echo "Certificate signing is not available on ${DU_FQDN}, keeping original certificate/key."
    fi
    return $return_code
}
