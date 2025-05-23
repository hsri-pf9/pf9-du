#!/bin/bash
set -e

# Arguments to the postinst script:
#script_name=$0
script_step=$1
configured_version=$2

change_file_permissions() {
    chown -R pf9:pf9group /var/log/pf9
    chown pf9:pf9group /etc/pf9/
    chown -R pf9:pf9group /etc/pf9/certs
    chown pf9:pf9group /etc/pf9/hostagent.conf
    chown -R pf9:pf9group /var/opt/pf9/
    chown -R pf9:pf9group /var/cache/pf9apps
    chmod 0440 /etc/sudoers.d/pf9-hostagent
    chmod 0550 /opt/pf9/hostagent/bin/pf9-apt
    chmod 0550 /opt/pf9/hostagent/bin/openport.py
    chmod 0550 /opt/pf9/hostagent/bin/jq
    chmod 0550 /opt/pf9/hostagent/pf9-hostagent-prestart.sh
}

cp /opt/pf9/hostagent/pf9-hostagent-systemd /lib/systemd/system/pf9-hostagent.service && systemctl daemon-reload

if [ "$script_step" = "configure" ] && [ -z $configured_version ]; then
    # Create the pf9 user and group
    grep ^pf9group: /etc/group > /dev/null 2>&1 || groupadd pf9group
    id pf9 > /dev/null 2>&1 || useradd -g pf9group -d /opt/pf9/home -s /usr/sbin/nologin --create-home -c "Platform9 user" pf9
    # In cases where pf9 user exists but is not part of the pf9group, explicitly
    # add them
    usermod -aG pf9group pf9
    # Add root also to the pf9group
    usermod -aG pf9group root
    # Make the certs and log files belong to the pf9group
    change_file_permissions
    systemctl enable pf9-hostagent > /dev/null 2>&1
elif [ "$script_step" = "configure" ]; then
    # During an upgrade, hostagent files are reverted to the default owner and
    # group. So, permissions must be reassigned.
    change_file_permissions
    # Restart comms in case certs were upgraded
    if [ -f /etc/init.d/pf9-comms ]; then
        service pf9-comms condrestart
    else
        systemctl condrestart pf9-comms
    fi
fi
