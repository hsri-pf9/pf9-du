#!/bin/bash

nettool=$(dirname $0)/../nettool.py


function format_print()
{
    local host=$1
    local status=$2

    local padlength=60
    local pad=$(printf '%0.1s' "-"{1..60})

    printf '%s' "${host} "
    printf '%*.*s' 0 $((padlength - ${#host})) "${pad}"
    printf '%s\n' "${status}"

}
function run_test()
{
    local expected_return_code=$1
    local host=$2
    local port=$3
    local proxy_host=$4
    local proxy_port=$5

    if [[ $proxy_host == "" ]]; then
        python $nettool --du-fqdn=$host --port=$port
    else
        python $nettool --du-fqdn=$host --port=$port\
                        --proxy-host=$proxy_host --proxy-port=$proxy_port
    fi

    if [[ $? == "${expected_return_code}" ]]; then
        format_print $host "OK"
        echo
    else
        format_print $host "FAILED"
        exit 1
    fi
}

run_test "0" pf9.platform9.net 443 squid.platform9.sys 3128
run_test "0" pf9.platform9.net 443
run_test "0" ipv4.google.com 443
run_test "0" 8.8.8.8 53
run_test "1" "no-such-host.platform9.com" 443
run_test "2" "pf9.platform9.net" 442
