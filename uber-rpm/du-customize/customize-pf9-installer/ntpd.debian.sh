function install_ntpd
{
    apt-get -y install ntp
    if [[ $? != "0" ]]; then
        echo "Error: Could not install the ntp package"
        return ${NTPD_INSTALL_FAILED}
    fi
    # NOTE the ntp service may time some time to update the clock
    ${SYSTEMCTL_CMD} start ntp
    ${SYSTEMCTL_CMD} is-active ntp
    if [[ $? != "0" ]]; then
        echo "Error: The ntp service failed to start"
        return ${NTPD_FAILED_TO_START}
    fi
}
