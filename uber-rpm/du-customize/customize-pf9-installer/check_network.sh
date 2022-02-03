#!/bin/bash
# Copyright (c) 2016 Platform9 Systems Inc.

source $(dirname $0)/globals.sh

# Exponential delay retry method. Useful for network related
function retry {
  local retries=$1
  shift

  local count=0
  until "$@"; do
    exit=$?
    wait=$((2 ** $count))
    count=$(($count + 1))
    if [ $count -lt $retries ]; then
      echo "Retry $count/$retries exited $exit, retrying in $wait seconds..."
      sleep $wait
    else
      echo "Retry $count/$retries exited $exit, no more retries left."
      return $exit
    fi
  done
  return 0
}

function check_network()
{
    echo "Checking network connectivity ..."
    if [[ "${PROXY_HOST}" == "" ]]; then
        # Retry for roughly 4 mins
        retry 8 ./nettool connect --host=${DU_FQDN} --port=443
    else
        # Retry for roughly 4 mins
        retry 8 ./nettool connect --proxy-host=${PROXY_HOST} --proxy-port=${PROXY_PORT} \
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
    return ${CONNECTION_FAILED}
}

function proxy_connection_failed()
{
    echo
    echo "Cannot connect to ${DU_FQDN} via ${PROXY_HOST}"
    echo "Exiting..."
    return ${CONNECTION_FAILED_VIA_PROXY}
}
