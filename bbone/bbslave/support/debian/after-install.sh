set -e

# Arguments to the postinst script:
#script_name=$0
script_step=$1
configured_version=$2

change_file_permissions() {
    chown -R pf9:pf9group /var/log/pf9
    chown -R pf9:pf9group /etc/pf9/
    chown -R pf9:pf9group /var/opt/pf9/
    chown -R pf9:pf9group /var/cache/pf9apps
    chmod 0440 /etc/sudoers.d/pf9-hostagent
    chmod 0550 /opt/pf9/hostagent/bin/pf9-apt
}

if [ "$script_step" = "configure" ] && [ -z $configured_version ]; then
    # Create the pf9 user and group
    grep ^pf9group: /etc/group > /dev/null 2>&1 || groupadd pf9group
    id pf9 > /dev/null 2>&1 || useradd -g pf9group -d / -s /usr/sbin/nologin -c "Platform9 user" pf9
    # In cases where pf9 user exists but is not part of the pf9group, explicitly
    # add them
    usermod -aG pf9group pf9
    # Add root also to the pf9group
    usermod -aG pf9group root
    # Make the certs and log files belong to the pf9group
    change_file_permissions
    update-rc.d pf9-hostagent defaults > /dev/null 2>&1
    service pf9-hostagent start
elif [ "$script_step" = "configure" ]; then
    # FIXME Since hostagent changed process names (to resolve conflicts with the
    # init script process name), the new init script may not be able to stop the
    # old hostagent process. This next 2 lines should be remove when the old
    # pf9-hostagent process no longer exists.
    /sbin/start-stop-daemon --stop --oknodo --quiet --retry 10 --name pf9-hostagent
    rm -f /var/run/pf9-hostagent*
    # During an upgrade, hostagent files are reverted to the default owner and
    # group. So, permissions must be reassigned.
    change_file_permissions
    # In case of an upgrade, restart the service
    service pf9-hostagent restart
fi
