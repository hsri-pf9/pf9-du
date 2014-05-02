Name:           pf9-hostagent-tarball
Version:        1.0.0
Release:        1.__GITHASH__
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
mkdir -p ${RPM_BUILD_ROOT}/opt/pf9/hostagent-tarball
cp %{SOURCE0} ${RPM_BUILD_ROOT}/opt/pf9/hostagent-tarball
mkdir -p ${RPM_BUILD_ROOT}/opt/pf9/du-customize
cp %{SOURCE1} ${RPM_BUILD_ROOT}/opt/pf9/du-customize

%clean
rm -rf ${RPM_BUILD_ROOT}

%files
%defattr(-,root,root,-)
/opt/pf9/hostagent-tarball
/opt/pf9/du-customize

%post

%preun

%postun

%changelog
