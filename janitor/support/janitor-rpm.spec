Name:           pf9-janitor
Version:        __VERSION__
Release:        __BUILDNUM__.__GITHASH__
Summary:        Platform 9 Maintenance Task Service

License:        Commercial
URL:            http://www.platform9.net

AutoReqProv:    no

Provides:       pf9-janitor
Requires:       sudo

BuildArch:      noarch
Group:          pf9-janitor

Source:         %{name}-%{version}.tgz

%define _unpackaged_files_terminate_build 0

%description
Platform 9 Maintenance Task Service

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
/opt/pf9/janitor
%dir /etc/pf9
%config /etc/pf9/janitor.conf
/etc/rc.d/init.d/
%dir /var/log/pf9

%post
if [ "$1" = "1" ]; then
    /sbin/chkconfig --add pf9-janitor
elif [ "$1" -ge "2" ]; then
    # In case of an upgrade, only restart the service if it's already running
    /sbin/service pf9-janitor condrestart
fi

%preun
if [ $1 = 0 ]; then # package is being erased, not upgraded
    /sbin/service pf9-janitor stop > /dev/null 2>&1
    /sbin/chkconfig --del pf9-janitor
fi

%postun

%changelog
