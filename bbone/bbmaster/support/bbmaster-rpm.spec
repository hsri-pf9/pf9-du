Name:           pf9-bbmaster
Version:        __VERSION__
Release:        __BUILDNUM__.__GITHASH__
Summary:        Platform 9 Backbone Master

License:        Commercial
URL:            http://www.platform9.com

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
%{__install} -D -m0644 pf9-bbmaster.service %{buildroot}%{_unitdir}/pf9-bbmaster.service

%clean
rm -rf ${RPM_BUILD_ROOT}

%files
%defattr(-,root,root,-)
/opt/pf9
%config /etc/pf9/bbmaster_config.py
%config /etc/pf9/bbmaster.conf
%dir /var/log/pf9
%{_unitdir}/pf9-bbmaster.service


%post
systemctl enable pf9-bbmaster.service

if [ "$1" -ge "2" ]; then
	#upgrade case
	systemctl restart pf9-bbmaster.service
fi

%preun

%postun

%changelog
