#!/bin/bash
# Copyright (c) 2016 Platform9 Systems Inc.

source $(dirname $0)/globals.sh

function check_network()
{
    if [[ "${PROXY_HOST}" == "" ]]; then
        python nettool.py --du-fqdn=${DU_FQDN} --port=443
    else
        python nettool.py --proxy-host=${PROXY_HOST} --proxy-port=${PROXY_PORT}\
                          --du-fqdn=${DU_FQDN} --port=443
    fi

    retval=$?
    if [[ $retval == "1" ]]; then
        dns_failed
    elif [[ $retval == "2" ]]; then
        connection_failed
    elif [[ $retval == "3" ]]; then
        proxy_connection_failed
    fi
}

function dns_failed()
{
    echo
    echo "DNS resolution failed!"
    echo "The Platform9 hostagent needs the host to be able to resolve domain names"
    echo "to work properly. Please make sure that you have a properly configured nameserver."
    echo "Exiting..."
    exit 1
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
