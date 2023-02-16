function install_ntpd
{
    # some of the hosts don't have the bc package installed
    yum -y install bc
    . /etc/os-release
    if (( $(echo "$VERSION_ID >= 8" | bc -lq) )); then
        setup_chronyd
    else
        setup_ntpd
    fi
}

function setup_chronyd
{
    dnf -y install chrony
    if [[ $? != "0" ]]; then
        echo "Error: Could not install the chrony package"
        return ${CHRONY_INSTALL_FAILED}
    fi
    ${SYSTEMCTL_CMD} start chronyd
    ${SYSTEMCTL_CMD} enable chronyd
    ${SYSTEMCTL_CMD} is-active chronyd
    if [[ $? != "0" ]]; then
        echo "Error: The chronyd service failed to start"
        return ${CHRONY_FAILED_TO_START}
    fi
}

function setup_ntpd
{
    yum -y install ntp
    if [[ $? != "0" ]]; then
        echo "Error: Could not install the ntp package"
        return ${NTPD_INSTALL_FAILED}
    fi
    ${SYSTEMCTL_CMD} start ntpd
    ${SYSTEMCTL_CMD} enable ntpd
    ${SYSTEMCTL_CMD} is-active ntpd
    if [[ $? != "0" ]]; then
        echo "Error: The ntpd service failed to start"
        return ${NTPD_FAILED_TO_START}
    fi
}
