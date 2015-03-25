#!/bin/bash
# Copyright (c) 2015 Platform9 Systems Inc.

function proxy_ask()
{
    while true; do
        read -p "Do you want to configure proxy settings? " yn
        case $yn in
            [Yy]* ) SETUP_PROXY="true"; _ask_proxy_settings; break;;
            [Nn]* ) SETUP_PROXY="false"; break;;
            *) echo "Please answer yes or no.";;
        esac
    done
}

function proxy_setup()
{
    local host=$1
    local port=$2

    echo "Setting up proxy with: "
    echo "host: $host"
    echo "proxy: $port"

    python ${JSON_TOOL} --inline --edit http_proxy.host  ${PF9_COMMS_CONF} $host
    python ${JSON_TOOL} --inline --edit http_proxy.port  ${PF9_COMMS_CONF} $port
}

function _ask_proxy_settings()
{
    echo
    echo "Please do not include 'http://' in front of the host"
    echo
    echo "Example: "
    echo "proxy host: squid.mycompany.com "
    echo "proxy port: 3128 "
    echo

    while true; do
        read -p "proxy host: " PROXY_HOST
        read -p "proxy port: " PROXY_PORT

        validate_proxyhost "${PROXY_HOST}"

        if [[ $? == "0" ]]; then # if it matches https?://
            echo
            echo "Please do not include 'http://' or 'https://' on your host"
            continue
        fi
        echo

        echo "These are your proxy settings:"
        echo "host: $PROXY_HOST"
        echo "port: $PROXY_PORT"

        read -p "Are these correct? " yn
        case $yn in
            [Yy]* ) break;;
            [Nn]* ) continue;;
            *) echo "Please answer yes or no.";;
        esac
    done
}

function validate_proxyhost()
{
    # Check if it begins with http:// or https://
    local host=$1
    echo $host | grep -E -q "^https?://"
    return $?
}
