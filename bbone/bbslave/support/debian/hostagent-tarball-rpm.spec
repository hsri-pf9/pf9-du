Name:           pf9-hostagent-tarball-debian
Version:        __VERSION__
Release:        __BUILDNUM__.__GITHASH__
Summary:        Platform 9 Host Agent tarball

License:        Commercial
URL:            http://www.platform9.net

AutoReqProv:    no

Provides:       pf9-hostagent-tarball-debian

BuildArch:      noarch
Group:          pf9-hostagent-tarball

Source0:        pf9-hostagent.tar.gz
Source1:        46-customize-hostagent-deb

%description
Platform 9 Host Agent tarball

%prep

%build

%install
mkdir -p ${RPM_BUILD_ROOT}/opt/pf9/hostagent-tarball/debian
cp %{SOURCE0} ${RPM_BUILD_ROOT}/opt/pf9/hostagent-tarball/debian
mkdir -p ${RPM_BUILD_ROOT}/opt/pf9/du-customize
cp %{SOURCE1} ${RPM_BUILD_ROOT}/opt/pf9/du-customize

%clean
rm -rf ${RPM_BUILD_ROOT}

%files
%defattr(-,root,root,-)
/opt/pf9/hostagent-tarball/debian
/opt/pf9/du-customize

%post

%preun

%postun

%changelog
