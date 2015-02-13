#!/bin/bash
# Copyright (c) 2015 Platform9 Systems Inc.

# This script builds the self-extracting installer

set -e -x

# el6      => Redhat 6.x | CentOS 6.x
# precise  => Ubuntu 12.04
DISTROS=(el6 precise)

# template name of the resulting installers
# Redhat 6.x | CentOS 6.x  => platform9-install-el6.sh
# and so on
BIN_NAME="platform9-install"

# directory where all packages to be bundled with
# the installer are found (packages.[el6|precise])
PACKAGES=${PACKAGES_LOCATION:-"/opt/pf9/www/private/packages"}

# where to put the resulting installers
LOCATION=${INSTALLER_LOCATION:-"/opt/pf9/www/private"}

PAYLOAD="payload"
PAYLOAD_TAR=${PAYLOAD}.tar

INSTALL_SCRIPT="installer"
DECOMPRESS_SCRIPT="decompress"
export TMP_INSTALLER=`mktemp /tmp/pf9-installer-XXXXX`

# replace identifier in the installer
# with a specific Linux distribution name
function customize_installer()
{
    local distro=$1

    sed -e "s/^DISTRO$/DISTRO='${distro}'/" \
            $INSTALL_SCRIPT > $TMP_INSTALLER
}

function setup_payload()
{
    local distro=$1
    local distro_install=${INSTALL_SCRIPT}.${distro}

    cp -rL ${PACKAGES}.${distro} ${PAYLOAD}.${distro}
    pushd ${PAYLOAD}.${distro}

    # copy the main install script
    cp $TMP_INSTALLER ${INSTALL_SCRIPT}
    # copy the distro specific install script
    cp ../${distro_install} ${distro_install}

    cp ../jsontool.py  jsontool.py
    cp ../support.common support.common
    cp ../support.${distro} support.${distro}

    chmod +x ${INSTALL_SCRIPT}
    tar cf ../${PAYLOAD_TAR}.${distro} ./*
    popd
}

function build_installer()
{
    local distro=$1
    local payload_tar="${PAYLOAD_TAR}.${distro}"
    local payload_tgz="${PAYLOAD_TAR}.${distro}.gz"
    local bin_name="${BIN_NAME}-${distro}.sh"

    # compress the payload
    if [ -e "${payload_tar}" ]; then
        gzip ${payload_tar}

        if [ -e "${payload_tgz}" ]; then
            cat ${DECOMPRESS_SCRIPT} ${payload_tgz} > ${bin_name}
            chmod +x ${bin_name}
        else
            echo "${payload_tgz} does not exist"
            exit 1
        fi
    else
        echo "${payload_tar} does not exist"
        exit 1
    fi
}

function main()
{
    for distro in "${DISTROS[@]}"
    do
        echo "Customizing installer for $distro"

        customize_installer "$distro"
        setup_payload       "$distro"
        build_installer     "$distro"

        echo "======================="

        # move the installers to a well-known location
        mv ${BIN_NAME}* ${LOCATION}
        rm -f ${TMP_INSTALLER}
    done
}

main
