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

REDHAT_VERSIONS=("6.5" "6.6")
UBUNTU_VERSIONS=("12.04")

function check_platform()
{
    if [[ `uname -m` != "x86_64" ]]; then
        echo "Sorry but we currently only support x86_64 machines"
        echo
        exit 1
    fi

    local version=""
    if [[ -f ${REDHAT_KNOWN_FILE} ]]; then
        # This only works for el6
        version=`awk '{print $3}' ${REDHAT_KNOWN_FILE}`
        _check_version "$version" REDHAT_VERSIONS

    elif [[ -f ${UBUNTU_KNOWN_FILE} ]]; then
        source ${UBUNTU_KNOWN_FILE}
        version=${DISTRIB_RELEASE}
        _check_version "$version" UBUNTU_VERSIONS

    else
        _print_not_supported
        exit 1
    fi
}

function _check_version()
{
    local version=$1
    local distro=$2[@]

    for distro_version in "${!distro}"
    do
        if [[ "${version}" == "${distro_version}" ]]; then
            return 0
        fi
    done
    _print_not_supported
    exit 1
}

function _print_not_supported()
{
    echo "Sorry but we currently do not support your platform."
    echo "Please let us know at support@platform9.com"
    echo
}
