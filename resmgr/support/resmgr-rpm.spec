Name:           pf9-resmgr
Version:        1.0.0
Release:        __BUILDNUM__.__GITHASH__
Summary:        Platform 9 Resource Manager

License:        Commercial
URL:            http://www.platform9.net

AutoReqProv:    no

Provides:       pf9-resmgr
Requires:       sudo

BuildArch:      noarch
Group:          pf9-resmgr

Source:         pf9-resmgr-1.0.0.tgz

%define _unpackaged_files_terminate_build 0

%description
Platform 9 Resource Manager

%prep
%setup -q

%build

%install
cp -r * ${RPM_BUILD_ROOT}

%clean
rm -rf ${RPM_BUILD_ROOT}

%files
%defattr(-,root,root,-)
%dir /opt/pf9
/opt/pf9/resmgr
/opt/pf9/du-customize
%dir /etc/pf9
%config /etc/pf9/resmgr.conf
%config /etc/pf9/resmgr-paste.ini
%config /etc/pf9/resmgr_config.py
/etc/rc.d/init.d/
%dir /var/log/pf9

%post
# assume that keystone is already in place with the admin key
pattern="^[ \t]*admin_token[ \t]*=[ \t]*.*";
adminkeyline=`grep "$pattern" /etc/keystone/keystone.conf`;
sed -i.orig "s/$pattern/$adminkeyline/g" /etc/pf9/resmgr-paste.ini
/sbin/chkconfig --add pf9-resmgr

%preun
if [ $1 = 0 ]; then # package is being erased, not upgraded
    /sbin/service pf9-resmgr stop > /dev/null 2>&1
    /sbin/chkconfig --del pf9-resmgr
fi

%postun

%changelog
