%global _python_bytecompile_errors_terminate_build 0

# Turn off the brp-python-bytecompile script
# It is recommended that if any python module needs specific
# byte compilation, it should be done manually.
# The rpm macro __os_install_post is defined to execute
# brp-python-bytecompile script which internally does python
# byte compile automatically. Below code removes the
# brp-python-bytecompile script from the __os_install_post macro,
# thus disabling the automatic python byte compile.
%global __os_install_post %(echo '%{__os_install_post}' | sed -e 's!/usr/lib[^[:space:]]*/brp-python-bytecompile[[:space:]].*$!!g')

Name:           pf9-hostagent
Version:        %{_version}
Release:        %{_release}
Summary:        Platform9 host agent

License:        Commercial
URL:            http://www.platform9.net

AutoReqProv:    no

Provides:       pf9-hostagent
Provides:       pf9-bbslave
Requires:       sudo
Requires:       procps-ng

# Hack to suppress PR IAAS-110
%define __prelink_undo_cmd %{nil}

%description
Platform9 host agent

%prep

%build

%install
SRC_DIR=%_src_dir

rm -fr $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT
cp -r $SRC_DIR/* $RPM_BUILD_ROOT/

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
/opt/pf9
%dir /var/cache/pf9apps
%attr(0440, root, root) /etc/sudoers.d/pf9-hostagent
%attr(0550, root, root) /opt/pf9/hostagent/bin/pf9-yum
%attr(0550, root, root) /opt/pf9/hostagent/bin/openport.py
%attr(0550, root, root) /opt/pf9/hostagent/bin/jq
%attr(0550, root, root) /opt/pf9/hostagent/pf9-hostagent-prestart.sh
%dir /var/opt/pf9
%dir /var/log/pf9
/etc/pf9/hostagent.conf
/etc/pf9/certs
%pre
if [ "$1" = "2" ]; then
    # In case of host upgrade get the latest hostgent.conf from DU.
    if [[ $(curl --retry 5 --silent -o /dev/null --head --write-out %{http_code} http://localhost:9080/private/hostagent.conf) == 200 ]]; then
        echo "Downloading hostagent.conf from PF9"
        if ! curl --fail --retry 5 --silent -o /etc/pf9/hostagent.conf.from.du http://localhost:9080/private/hostagent.conf; then
            # Failed to download the hostagent.conf from DDU
            echo "Failed to download hostagent.conf from PF9"
            exit 1
        fi
    else
        echo "Failed to check existence hostagent.conf from PF9"
        exit 1
    fi
    # Take a backup of certs directory
    if [ -d "/etc/pf9/certs" ]; then
        echo "Creating a backup of certs directory"
        rm -rf /etc/pf9/certs.bkup
        cp -r /etc/pf9/certs /etc/pf9/certs.bkup
    fi
fi

%post
set -e

change_file_permissions() {
    chown -R pf9:pf9group /var/log/pf9
    chown pf9:pf9group /etc/pf9/
    chown -R pf9:pf9group /etc/pf9/certs
    chown pf9:pf9group /etc/pf9/hostagent.conf
    chown -R pf9:pf9group /var/opt/pf9/
    chown -R pf9:pf9group /var/cache/pf9apps
}

cp /opt/pf9/hostagent/pf9-hostagent-systemd /lib/systemd/system/pf9-hostagent.service && systemctl daemon-reload

if [ "$1" = "1" ]; then
    # Create the pf9 user and group
    grep ^pf9group: /etc/group &>/dev/null || groupadd pf9group
    homedir=/opt/pf9/home
    id pf9 &>/dev/null || useradd -g pf9group -d ${homedir} -s /sbin/nologin --create-home -c "Platform9 user" pf9 || true
    # Create pf9 home directory ourselves if necessary due to IAAS-4714
    source /opt/pf9/hostagent/bin/create_pf9_homedir.sh
    create_pf9_homedir_if_absent ${homedir}

    # In cases where pf9 user exists but is not part of the pf9group, explicitly
    # add them
    usermod -aG pf9group pf9
    # Add root also to the pf9group
    usermod -aG pf9group root
    change_file_permissions

    systemctl enable pf9-hostagent
elif [ "$1" = "2" ]; then
    # During an upgrade, hostagent files are reverted to the default owner and
    # group. So, permissions must be reassigned.
    change_file_permissions
    # Restart comms in case certs were upgraded
    if [ -f /etc/init.d/pf9-comms ]; then
        service pf9-comms condrestart
    else
        systemctl condrestart pf9-comms
    fi

    systemctl enable pf9-hostagent
fi

%preun
# $1==0: remove the last version of the package
# $1==1: install the first time
# $1>=2: upgrade


if [ "$1" = 0 ]; then
    systemctl stop pf9-hostagent
    systemctl disable pf9-hostagent
    rm /lib/systemd/system/pf9-hostagent.service && systemctl daemon-reload
fi

%postun
# The cache clean up will be done with uninstall and upgrade
# of the hostagent.
rm -rf "/var/opt/pf9/hostagent"

# Remove the apps cache in case of an uninstall
if [ "$1" = "0" ]; then
    rm -rf "/var/cache/pf9apps"
    pkill pf9-sidekick || true
fi

%posttrans
# Replacing hostagent.conf and certs should be part of posttrans as files are
# deleted after execution of postinst scriplet. Please refer rpm scriplet
# ordering guide.
# In posttrans scriplets, $1 passed is always 0 for both upgrade and install.

change_file_permissions() {
    chown -R pf9:pf9group /var/log/pf9
    chown pf9:pf9group /etc/pf9/
    chown -R pf9:pf9group /etc/pf9/certs
    chown pf9:pf9group /etc/pf9/hostagent.conf
    chown -R pf9:pf9group /var/opt/pf9/
    chown -R pf9:pf9group /var/cache/pf9apps
}

# Replace the hostagent.conf with the one downloaded from DDU.
if [ -f "/etc/pf9/hostagent.conf.from.du" ]; then
    echo "Replacing the hostagent.conf with the one downloaded from the DDU"
    # backup the previous hostagent conf, in case there were any custom changes
    cp /etc/pf9/hostagent.conf /etc/pf9/hostagent.conf.$(date +"%Y-%m-%d-%H-%M").bkup || true
    mv -f /etc/pf9/hostagent.conf.from.du /etc/pf9/hostagent.conf
fi
# Check if we have created a backup of certs directory
if [ -d "/etc/pf9/certs.bkup" ]; then
    # Check if the certs diretory does not exists or is empty
    if [ ! -d /etc/pf9/certs ] || [ ! "$(ls -A "/etc/pf9/certs/ca")" ] || [ ! "$(ls -A "/etc/pf9/certs/hostagent")" ]; then
        echo "Restoring the certs directory from the backup"
        rm -rf /etc/pf9/certs
        mv -f /etc/pf9/certs.bkup /etc/pf9/certs
    fi
    # delete the backed-up certs directory
    rm -rf /etc/pf9/certs.bkup
fi
# Change the file permission so that PF9 services can access them
change_file_permissions


%changelog
