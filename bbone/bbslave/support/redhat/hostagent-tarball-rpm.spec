Name:           pf9-hostagent-tarball
Version:        __VERSION__
Release:        __BUILDNUM__.__GITHASH__
Summary:        Platform 9 Host Agent tarball

License:        Commercial
URL:            http://www.platform9.net

AutoReqProv:    no

Provides:       pf9-hostagent-tarball

BuildArch:      noarch
Group:          pf9-hostagent-tarball

Source0:        pf9-hostagent.tar.gz
Source1:        45-customize-hostagent-rpm

%description
Platform 9 Host Agent tarball

%prep

%build

%install
mkdir -p ${RPM_BUILD_ROOT}/opt/pf9/hostagent-tarball/redhat
cp %{SOURCE0} ${RPM_BUILD_ROOT}/opt/pf9/hostagent-tarball/redhat
mkdir -p ${RPM_BUILD_ROOT}/opt/pf9/du-customize
cp %{SOURCE1} ${RPM_BUILD_ROOT}/opt/pf9/du-customize

%clean
rm -rf ${RPM_BUILD_ROOT}

%files
%defattr(-,root,root,-)
/opt/pf9/hostagent-tarball/redhat
/opt/pf9/du-customize

%post

%preun

%postun

%changelog
