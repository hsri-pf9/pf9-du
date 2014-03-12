Name:           pf9-bbmaster
Version:        1.0.0
Release:        1
Summary:        Platform 9 Backbone Master

License:        Commercial
URL:            http://www.platform9.net

AutoReqProv:    no

Provides:       pf9-bbone-master
Requires:       sudo

BuildArch:      noarch
Group:          pf9-bbone

Source:         pf9-bbmaster-1.0.0.tgz

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
/etc/pf9
/etc/init.d/pf9-bbmaster


%post

%preun

%postun

%changelog
