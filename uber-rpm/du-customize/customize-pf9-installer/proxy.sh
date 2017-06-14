#!/bin/bash
# Copyright (c) 2015 Platform9 Systems Inc.

function proxy_ask()
{
    read -p "Do you want to configure proxy settings (yes/no)? " yn
    case $yn in
        [Yy]* ) SETUP_PROXY="true"; _ask_proxy_settings; return 0;;
        [Nn]* ) SETUP_PROXY="false"; return 0;;
        *) echo "Please answer yes or no."; exit 1;;
    esac
}

function proxy_setup()
{
    local host=$1
    local port=$2

    if [[ -z "${host}" || -z "${port}" ]]; then
      echo "Skipping proxy setup since the proxy host or the proxy port is not set."
      return
    fi

    echo "Setting up proxy with: "
    echo "host: $host"
    echo "port: $port"

    echo "{\"http_proxy\":{\"host\":\"$host\", \"port\":$port}}" > ${PF9_COMMS_PROXY_CONF}
}

function _ask_proxy_settings()
{
    echo
    echo "Example: "
    echo "proxy host: squid.mycompany.com "
    echo "proxy port: 3128 "
    echo

    while true; do
        read -p "proxy host: " PROXY_HOST
        read -p "proxy port: " PROXY_PORT

        echo "Stripping http/https schema..."
        echo
        PROXY_HOST=$(strip_http_schema "${PROXY_HOST}")

        echo "These are your proxy settings:"
        echo "host: \"$PROXY_HOST\""
        echo "port: \"$PROXY_PORT\""

        if [[ -z "${PROXY_HOST}" || -z "${PROXY_PORT}" ]]; then
          echo "Skipping proxy setup since the proxy host or the proxy port is not set."
          SETUP_PROXY="false"
        fi

        read -p "Are these correct? (yes/no) " yn
        case $yn in
            [Yy]* ) break;;
            [Nn]* ) continue;;
            *) echo "Please answer yes or no.";;
        esac
    done
}

function strip_http_schema()
{
    local proxy_host=$1
    if echo $proxy_host | grep -E -q "^https?://"; then
        proxy_host=$(echo $proxy_host | sed -n -e 's/^https\?\:\/\///p')
    fi
    echo $proxy_host
}

