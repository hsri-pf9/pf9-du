function install_ntpd
{
    yum -y install ntp
    if [[ $? != "0" ]]; then
        echo "Error: Could not install the ntp package"
        exit 1
    fi
    systemctl start ntpd
    systemctl enable ntpd
    systemctl status ntpd
    if [[ $? != "0" ]]; then
        echo "Error: The ntpd service failed to start"
        exit 1
    fi
}
