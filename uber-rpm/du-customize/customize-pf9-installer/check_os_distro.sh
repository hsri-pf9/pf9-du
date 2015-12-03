#!/usr/bin/bash
# Copyright (c) 2015 Platform9 Systems Inc.

# If we have redhat|centos|scientific-linux
REDHAT_KNOWN_FILE="/etc/redhat-release"
# Example: CentOS 6.6:
# CentOS release 6.6 (Final)
#
# Example: CentOS 7  :
# CentOS Linux release 7.0.1406 (Core)
UBUNTU_KNOWN_FILE="/etc/lsb-release"
# Example Ubuntu 12.04:
#
# DISTRIB_ID=Ubuntu
# DISTRIB_RELEASE=12.04
# DISTRIB_CODENAME=precise
# DISTRIB_DESCRIPTION="Ubuntu 12.04.5 LTS"

REDHAT_VERSIONS=("6.5" "6.6" "6.7" "7.0" "7.1")
UBUNTU_VERSIONS=("12.04" "14.04")

function check_platform()
{
    echo "Checking the machine's architecture"
    if [[ `uname -m` != "x86_64" ]]; then
        echo "Sorry but we currently only support x86_64 (64-bit) machines"
        echo
        exit 1
    fi

    local version=""
    if [[ -f ${REDHAT_KNOWN_FILE} ]]; then
        echo "Operating system belongs to the Redhat family"
        _check_version "${REDHAT_KNOWN_FILE}" REDHAT_VERSIONS
        if [[ $? != "0" ]]; then
            _print_not_supported
        fi
    elif [[ -f ${UBUNTU_KNOWN_FILE} ]]; then
        echo "Operating system is Ubuntu"
        _check_version "${UBUNTU_KNOWN_FILE}" UBUNTU_VERSIONS
        if [[ $? != "0" ]]; then
            _print_not_supported
        fi
    else
        _print_not_supported
    fi
}

function _check_version()
{
    echo "Checking operating system version/release"
    local file=$1
    local distro=$2[@]

    for distro_version in "${!distro}"
    do
        echo "Checking if operating system version is ${distro_version}"
        grep -q "${distro_version}" ${file}
        if [[ $? == "0" ]]; then
            echo "Operating system is supported"
            return 0
        fi
    done
    echo "Operating system is not supported"
    return 1
}

function _print_not_supported()
{
    if [[ "${SKIP_OS_CHECK}" == "true" ]]; then
        return 0
    fi

    echo "Sorry but we currently do not support your operating system."
    echo "Please let us know at support@platform9.com"
    echo

    while true; do
        read -p "Do you still want to continue? (yes/no) " yn
        case $yn in
            [Yy]* ) break;;
            [Nn]* ) exit 0;;
            *) echo "Please answer yes or no.";;
        esac
    done
}
