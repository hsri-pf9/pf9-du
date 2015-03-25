#!/bin/bash

source $(dirname $0)/../proxy.sh

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
function test_host()
{
    local expected_return_code=$1
    local host=$2

    validate_proxyhost $host
    if [[ $? == "${expected_return_code}" ]]; then
        format_print $host "OK"
    else
        format_print $host "FAILED"
    fi
}

echo "The strings below should pass the validation"
test_host "1" "squid.company.com"
test_host "1" "http.company.com"
test_host "1" "https.company.com"
test_host "1" "http/.company.com"
test_host "1" "http:/.company.com"
test_host "1" "httppppp://.company.com"
test_host "1" "httpssss://wat.company.com"
test_host "1" "squid.http://company.com"
test_host "1" "squid://.company.com"
echo

echo "The strings below should fail the validation"
test_host "0" "https://squid.company.com"
test_host "0" "http://squid.company.com"
test_host "0" "http://squid.b.a.company.com"
echo
