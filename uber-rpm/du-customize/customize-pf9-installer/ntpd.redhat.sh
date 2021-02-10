function install_ntpd
{
    . /etc/os-release
    if [[ "$VERSION_ID" == "8" ]]; then
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
        exit 1
    fi
    ${SYSTEMCTL_CMD} start chronyd
    ${SYSTEMCTL_CMD} enable chronyd
    ${SYSTEMCTL_CMD} is-active chronyd
    if [[ $? != "0" ]]; then
        echo "Error: The chronyd service failed to start"
        exit 1
    fi
}

function setup_ntpd
{
    yum -y install ntp
    if [[ $? != "0" ]]; then
        echo "Error: Could not install the ntp package"
        exit 1
    fi
    ${SYSTEMCTL_CMD} start ntpd
    ${SYSTEMCTL_CMD} enable ntpd
    ${SYSTEMCTL_CMD} is-active ntpd
    if [[ $? != "0" ]]; then
        echo "Error: The ntpd service failed to start"
        exit 1
    fi
}
