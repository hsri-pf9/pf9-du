#!/bin/bash

nettool="$1"


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

function test_connect_success()
{
    local host=$2
    "$nettool" connect "$@"

    if [[ $? == 0 ]]; then
        format_print $host "OK"
    else
        format_print $host "FAILED"
        exit 1
    fi
}

function test_connect_fail()
{
    local expected="$1"
    local host=$3
    shift

    local actual
    actual="$("$nettool" connect "$@" 2>&1)"

    if [[ $? != 1 ]] || ! [[ "${actual}" =~ "${expected}" ]]; then
        echo "expected: ${expected}"
        echo "actual: ${actual}"
        format_print $host "FAILED"
        exit 1
    else
        format_print $host "OK"
    fi
}

function test_urlparse_success() {
    local url="$1"
    local expected="$2"

    local actual="$("$nettool" urlparse "$url")"

    if [[ $? != 0 ]] || [[ "${actual}" != "${expected}" ]]; then

        echo "expected: ${expected}"
        echo "actual: ${actual}"

        format_print $url "FAILED"
        exit 1
    fi
    format_print $url "OK"

}

function test_urlparse_fail() {
    local url="$1"
    local expected="$2"

    local actual
    actual="$("$nettool" urlparse "$url" 2>&1)"

    if [[ $? != 1 ]] || ! [[ "${actual}" =~ "${expected}" ]]; then
        echo "expected: ${expected}"
        echo "actual: ${actual}"
        format_print $url "FAILED"
        exit 1
    fi
    format_print $url "OK"

}

function main()
{
    if [[ -z "${nettool}" ]]; then
        echo "Usage: $0 <Nettool program>"
        exit 1
    fi

    # Test direct connects
    test_connect_success --host df.platform9.net --port 443
    test_connect_success --host ipv4.google.com --port 443
    test_connect_success --host 8.8.8.8 --port 53

    # Test http proxy connect
    test_connect_success --host df.platform9.net --port 443 \
        --proxy-host squid-01.platform9.horse --proxy-port 3128

    # Test https proxy connect
    test_connect_success --host df.platform9.net --port 443 \
        --proxy-protocol https --proxy-host squid-01.platform9.horse --proxy-port 443

    # Test http proxy with basic auth connect
    test_connect_success --host df.platform9.net --port 443 \
        --proxy-host squid-basic-auth-01.platform9.horse --proxy-port 3128 \
        --proxy-user pf9 --proxy-pass dummy

    # Test https proxy with basic auth connect
    test_connect_success --host df.platform9.net --port 443 \
        --proxy-protocol https --proxy-host squid-basic-auth-01.platform9.horse --proxy-port 443 \
        --proxy-user pf9 --proxy-pass dummy


    # Test unresolvable hostnames
    test_connect_fail "no such host" --host "no-such-host.platform9.com" --port 443
    test_connect_fail "503 Service Unavailable" --host "no-such-host.platform9.com" --port 443 \
        --proxy-host squid-01.platform9.horse
    test_connect_fail "503 Service Unavailable" --host "no-such-host.platform9.com" --port 443 \
        --proxy-host squid-01.platform9.horse --proxy-protocol https --proxy-port 443
    test_connect_fail "503 Service Unavailable" --host "no-such-host.platform9.com" --port 443 \
        --proxy-host squid-basic-auth-01.platform9.horse --proxy-user pf9 --proxy-pass dummy
    test_connect_fail "503 Service Unavailable" --host "no-such-host.platform9.com" --port 443 \
        --proxy-host squid-basic-auth-01.platform9.horse --proxy-user pf9 --proxy-pass dummy \
        --proxy-protocol https --proxy-port 443

    # Test connection timeouts
    test_connect_fail "connection timed out" --host "df.platform9.net" --port 442

    # Test invalid passwords
    test_connect_fail "407 Proxy Authentication Required" --host "df.platform9.net" --port 443 \
        --proxy-host squid-basic-auth-01.platform9.horse --proxy-user pf9 --proxy-pass wrongPassword \
        --proxy-protocol https --proxy-port 443
    test_connect_fail "407 Proxy Authentication Required" --host "df.platform9.net" --port 443 \
        --proxy-host squid-basic-auth-01.platform9.horse --proxy-user wrongUser --proxy-pass dummy


    test_urlparse_success http://squid.platform9.net:3128 "http squid.platform9.net 3128"
    test_urlparse_success squid.platform9.net:3128 "http squid.platform9.net 3128"
    test_urlparse_success squid.platform9.net "http squid.platform9.net 3128"
    test_urlparse_success https://squid.platform9.net "https squid.platform9.net 3128"
    test_urlparse_success https://squid.platform9.net:443 "https squid.platform9.net 443"
    test_urlparse_success http://[fc00:1:a:1:f816:3eff:fe84:1e0e]:3128 "http [fc00:1:a:1:f816:3eff:fe84:1e0e] 3128"
    test_urlparse_success https://[fc00:1:a:1:f816:3eff:fe84:1e0e]:3128 "https [fc00:1:a:1:f816:3eff:fe84:1e0e] 3128"
    test_urlparse_success http://[fc00:1:a:1:f816:3eff:fe84:1e0e] "http [fc00:1:a:1:f816:3eff:fe84:1e0e] 3128"
    test_urlparse_success http://[fc00:1:a:2::48] "http [fc00:1:a:2::48] 3128"
    test_urlparse_success http://[::1] "http [::1] 3128"

    test_urlparse_success http://pf9:dummyPass@squid.platform9.net:3128 \
        "http squid.platform9.net 3128 pf9 dummyPass"
    test_urlparse_success https://pf9:dummyPass@[fc00:1:a:1:f816:3eff:fe84:1e0e]:3128 \
        "https [fc00:1:a:1:f816:3eff:fe84:1e0e] 3128 pf9 dummyPass"
    test_urlparse_success df@platform9.net:dummyAgain@squid.platform9.net:3128 \
        "http squid.platform9.net 3128 df@platform9.net dummyAgain"
    test_urlparse_success usernames:cant:have:colons@squid.platform9.net \
        "http squid.platform9.net 3128 usernames cant:have:colons"
    test_urlparse_success df@platform9.net:dummy:again@squid.platform9.net \
        "http squid.platform9.net 3128 df@platform9.net dummy:again"
    test_urlparse_success https://squid.platform9.net \
        "https squid.platform9.net 3128"
    test_urlparse_success https://squid.platform9.net:443 \
        "https squid.platform9.net 443"

    test_urlparse_fail http://squid.platform9.net:portstring "invalid port \":portstring\" after host"
    test_urlparse_fail nopassword@squid.platform9.net "Password not found in user info"
    test_urlparse_fail ftp://squid.platform9.net "Invalid protocol: ftp"
    test_urlparse_fail squid.platform9.net:80:82 "too many colons in address"
    test_urlparse_fail http://1:2:3:4:5:6:80 "too many colons in address"
    test_urlparse_fail http://[1:2:3:4:5:6:80 "missing ']' in host"
    test_urlparse_fail https://1:2:3:4:5:6]:80 "too many colons in address"
}

main
