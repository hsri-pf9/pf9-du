Name:           pf9-hostagent
Version:        %{_version}
Release:        %{_release}
Summary:        Platform 9 host agent

License:        Commercial
URL:            http://www.platform9.net

AutoReqProv:    no

Provides:       pf9-hostagent
Provides:       pf9-bbslave
Requires:       python-setuptools
Requires:       sudo

# Hack to suppress PR IAAS-110
%define __prelink_undo_cmd %{nil}

%description
Platform 9 host agent

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
/etc/rc.d/init.d/pf9-hostagent
%dir /var/cache/pf9apps
%attr(0440, root, root) /etc/sudoers.d/pf9-hostagent
%attr(0550, root, root) /opt/pf9/hostagent/bin/pf9-yum
%attr(0550, root, root) /opt/pf9/hostagent/bin/openport.py
%dir /var/opt/pf9
%config /etc/pf9/hostagent.conf
/etc/pf9/certs
%dir /var/log/pf9

%post
change_file_permissions() {
    chown -R pf9:pf9group /var/log/pf9
    chown pf9:pf9group /etc/pf9/
    chown -R pf9:pf9group /etc/pf9/certs
    chown pf9:pf9group /etc/pf9/hostagent.conf
    chown -R pf9:pf9group /var/opt/pf9/
    chown -R pf9:pf9group /var/cache/pf9apps
}

if [ "$1" = "1" ]; then
    # Create the pf9 user and group
    grep ^pf9group: /etc/group &>/dev/null || groupadd pf9group
    id pf9 &>/dev/null || useradd -g pf9group -d /opt/pf9/home -s /sbin/nologin --create-home -c "Platform9 user" pf9
    # In cases where pf9 user exists but is not part of the pf9group, explicitly
    # add them
    usermod -aG pf9group pf9
    # Add root also to the pf9group
    usermod -aG pf9group root
    change_file_permissions
    chkconfig --add pf9-hostagent
elif [ "$1" = "2" ]; then
    # During an upgrade, hostagent files are reverted to the default owner and
    # group. So, permissions must be reassigned.
    change_file_permissions
    # Restart comms in case certs were upgraded
    service pf9-comms condrestart
    # In case of an upgrade, restart the service if it's running
    service pf9-hostagent condrestart
fi

%preun
# $1==0: remove the last version of the package
# $1==1: install the first time
# $1>=2: upgrade
if [ "$1" = 0 ]; then
    service pf9-hostagent stop > /dev/null
    chkconfig --del pf9-hostagent
fi

%postun
# The cache clean up will be done with uninstall and upgrade
# of the hostagent.
rm -rf "/var/opt/pf9/hostagent"

# Remove the apps cache in case of an uninstall
if [ "$1" = "0" ]; then
    rm -rf "/var/cache/pf9apps"
fi

%changelog
