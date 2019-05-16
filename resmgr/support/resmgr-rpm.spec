Name:           pf9-resmgr
Version:        __VERSION__
Release:        __BUILDNUM__.__GITHASH__
Summary:        Platform 9 Resource Manager

License:        Commercial
URL:            http://www.platform9.com

AutoReqProv:    no

Provides:       pf9-resmgr
Requires:       sudo

BuildArch:      noarch
Group:          pf9-resmgr

Source:         %{name}-%{version}.tgz

%define _unpackaged_files_terminate_build 0

%description
Platform 9 Resource Manager

%prep
%setup -q

%build

%install
cp -r * ${RPM_BUILD_ROOT}
%{__install} -D -m0644 pf9-resmgr.service %{buildroot}%{_unitdir}/pf9-resmgr.service

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
/etc/pf9/resmgr_roles
/etc/pf9/resmgr_svc_configs
%dir /var/log/pf9
%{_unitdir}/pf9-resmgr.service

%post
if [ "$1" = "1" ]; then
    # assume that keystone is already in place with the admin key
    pattern="^[ \t]*admin_token[ \t]*=[ \t]*.*";
    adminkeyline=`grep "$pattern" /etc/keystone/keystone.conf`;
    sed -i.orig "s/$pattern/$adminkeyline/g" /etc/pf9/resmgr-paste.ini
fi

%preun
if [ $1 = 0 ]; then # package is being erased, not upgraded
    systemctl stop pf9-resmgr.service
    systemctl disable pf9-resmgr.service
fi

%postun

%changelog
