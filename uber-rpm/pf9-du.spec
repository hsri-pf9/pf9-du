Summary:          Platform9 deployment unit
Name:             pf9-du
Version:          __VERSION__
Release:          __BUILDNUM__.__GITHASH__
Group:            Applications/System
License:          Commercial
URL:              http://www.platform9.net/
Source0:          %{name}-%{version}.tar.gz
BuildArch:        noarch
Requires: pf9-resmgr
Requires: pf9-bbmaster
Requires: pf9-clarity
Requires: pf9-hostagent-tarball
Requires: pf9-hostagent-tarball-debian
Requires: pf9-ostackhost-wrapper
Requires: pf9-ostackhost-wrapper-debian
Requires: pf9-notifications
Requires: pf9-janitor
Requires: pf9-switcher

%description
Platform9 deployment unit.

%prep
%setup -q

%build

%install
mkdir -p %{buildroot}/opt/pf9/du-customize
cp -rp * %{buildroot}

%files
%defattr(-,root,root,-)
/opt/pf9/du-customize
%config /etc/pf9/global.conf
