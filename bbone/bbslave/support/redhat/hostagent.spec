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
Requires:       python-setuptools
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
%attr(0550, root, root) /opt/pf9/hostagent/pf9-hostagent-prestart.sh
%dir /var/opt/pf9
%config /etc/pf9/hostagent.conf
/etc/pf9/certs
%dir /var/log/pf9

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

%changelog
