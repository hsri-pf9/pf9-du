#!/bin/bash
# Copyright (c) 2015 Platform9 Systems Inc.

# This script builds the self-extracting installer

set -e -x

# redhat  => Redhat 6.x | CentOS 6.x | Redhat 7.x | CentOS 7.x
# debian  => Ubuntu 12.04 | Ubuntu 14.04
DISTROS=(debian redhat)

# template name of the resulting installers
# Redhat 6.x | CentOS 6.x  => platform9-install-redhat.sh
# and so on
BIN_NAME="platform9-install"

# directory where all packages to be bundled with
# the installer are found (packages.[redhat|debian])
PACKAGES=${PACKAGES_LOCATION:-"/opt/pf9/www/private/packages"}

# where to put the resulting installers
LOCATION=${INSTALLER_LOCATION:-"/opt/pf9/www/private"}

PAYLOAD="payload"
PAYLOAD_TAR=${PAYLOAD}.tar

INSTALL_SCRIPT="installer"
GLOBALS_SCRIPT="globals.sh"
DECOMPRESS_SCRIPT="decompress"
export TMP_INSTALLER=`mktemp /tmp/pf9-installer-XXXXX`
export TMP_GLOBALS=`mktemp /tmp/pf9-globals-XXXXX`

# replace identifier in the installer
# with a specific Linux distribution name
function customize_installer()
{
    local distro=$1
    local du_fqdn=$2

    sed -e "s/__DISTRO__/'${distro}'/" \
            $INSTALL_SCRIPT > $TMP_INSTALLER

    sed -e "s/__DU_FQDN__/'${du_fqdn}'/" \
            $GLOBALS_SCRIPT > $TMP_GLOBALS
}

function setup_payload()
{
    local distro=$1
    local distro_install=${INSTALL_SCRIPT}.${distro}

    rm -rf ${PAYLOAD}.${distro}
    cp -rL ${PACKAGES}.${distro} ${PAYLOAD}.${distro}
    pushd ${PAYLOAD}.${distro}

    # copy the main install script
    cp $TMP_INSTALLER ${INSTALL_SCRIPT}
    cp $TMP_GLOBALS ${GLOBALS_SCRIPT}
    # copy the distro specific install script
    cp ../${distro_install} ${distro_install}

    cp ../wait.sh wait.sh
    cp ../proxy.sh proxy.sh
    cp ../ntpd.sh ntpd.sh
    cp ../ntpd.${distro}.sh ntpd.${distro}.sh
    cp ../support.sh support.sh
    cp ../jsontool.py  jsontool.py
    cp ../nettool.py nettool.py
    cp ../check_os_distro.sh  check_os_distro.sh
    cp ../check_sudoers.sh  check_sudoers.sh
    cp ../check_ports.sh check_ports.sh
    cp ../check_network.sh  check_network.sh
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
        gzip -f ${payload_tar}

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
    # used for checking DNS resolution
    local du_fqdn=$1
    for distro in "${DISTROS[@]}"
    do
        echo "Customizing $distro installer for $du_fqdn"

        customize_installer "$distro" "$du_fqdn"
        setup_payload       "$distro"
        build_installer     "$distro"

        echo "======================="

        # move the installers to a well-known location
        mv ${BIN_NAME}* ${LOCATION}
        rm -f ${TMP_INSTALLER}
        rm -f ${TMP_GLOBALS}
    done
}

if [[ $# != "1" ]]; then
   echo "usage: $0 <DU_FQDN>"
   exit 1
fi

main $@
