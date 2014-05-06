Name:           pf9-hostagent
Version:        __VERSION__
Release:        1.__GITHASH__
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
/etc/init.d/pf9-hostagent
/etc/pf9

%post
if [ "$1" = "1" ]; then
    # Create the pf9 user and group
    id pf9 &>/dev/null || useradd pf9
    grep ^pf9group: /etc/group &>/dev/null || groupadd pf9group
    usermod -aG pf9group pf9
    # Add root also to the pf9group
    usermod -aG pf9group root

    # Make the certs file belong to the pf9group
    chgrp -R pf9group /etc/pf9/certs/*

    chkconfig --add pf9-hostagent
    service pf9-hostagent start
elif [ "$1" = "2" ]; then
    # In case of an upgrade, only restart the service
    service pf9-hostagent restart
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
