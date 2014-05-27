Name:           pf9-bbmaster
Version:        __VERSION__
Release:        __BUILDNUM__.__GITHASH__
Summary:        Platform 9 Backbone Master

License:        Commercial
URL:            http://www.platform9.net

AutoReqProv:    no

Provides:       pf9-bbone-master
Requires:       sudo

BuildArch:      noarch
Group:          pf9-bbone

Source:         %{name}-%{version}.tgz

%define _unpackaged_files_terminate_build 0

%description
Platform 9 backbone master

%prep
%setup -q

%build

%install
cp -r * ${RPM_BUILD_ROOT}

%clean
rm -rf ${RPM_BUILD_ROOT}

%files
%defattr(-,root,root,-)
/opt/pf9
%config /etc/pf9/bbmaster_config.py
%config /etc/pf9/bbmaster.conf
/etc/rc.d/init.d/pf9-bbmaster
%dir /var/log/pf9


%post
# Ugly hack to get pf9-bbmaster hooked up to init.d scripts
sudo /bin/ln -sf /opt/pf9/bbmaster/bin/python /opt/pf9/bbmaster/bin/pf9-bbmaster

if [ "$1" -ge "2" ]; then
    # In case of an upgrade, restart the service if it's already running
    /sbin/service pf9-bbmaster condrestart
fi

%preun

%postun

%changelog
