Summary:          Platform9 deployment unit
Name:             pf9-du
Version:          __VERSION__
Release:          __BUILDNUM__.__GITHASH__
Group:            Applications/System
License:          Commercial
URL:              http://www.platform9.net/
Source0:          %{name}-%{version}.tar.gz
BuildArch:        noarch

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
