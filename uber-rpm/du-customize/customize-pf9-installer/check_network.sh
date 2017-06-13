#!/bin/bash
# Copyright (c) 2016 Platform9 Systems Inc.

source $(dirname $0)/globals.sh

function check_network()
{
    if [[ "${PROXY_HOST}" == "" ]]; then
        ./nettool connect --host=${DU_FQDN} --port=443
    else
        ./nettool connect --proxy-host=${PROXY_HOST} --proxy-port=${PROXY_PORT} \
                          --host=${DU_FQDN} --port=443 --proxy-protocol=${PROXY_PROTOCOL} \
                          --proxy-user=${PROXY_USER} --proxy-pass=${PROXY_PASS}
    fi

    retval=$?
    if [[ $retval != "0" ]]; then
        if [[ "${PROXY_HOST}" == "" ]]; then
            connection_failed
        else
            proxy_connection_failed
        fi
    fi
}

function connection_failed()
{
    echo
    echo "Cannot connect to ${DU_FQDN}"
    echo "Exiting..."
    exit 1
}

function proxy_connection_failed()
{
    echo
    echo "Cannot connect to ${DU_FQDN} via ${PROXY_HOST}"
    echo "Exiting..."
    exit 1
}
