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

    python ${JSON_TOOL} --inline --edit http_proxy.host  ${PF9_COMMS_CONF} $host > /dev/null 2>&1
    python ${JSON_TOOL} --inline --edit http_proxy.port  ${PF9_COMMS_CONF} $port > /dev/null 2>&1
}

function _ask_proxy_settings()
{
    while true; do
        read -p "proxy host: " PROXY_HOST
        read -p "proxy port: " PROXY_PORT

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
