Summary:          Platform9 deployment unit
Name:             pf9-du
Version:          1.0.0
Release:          1.__GITHASH__
Group:            Applications/System
License:          Commercial
URL:              http://www.platform9.net/
Source0:          %{name}-%{version}.tar.gz
BuildArch:        noarch
#BuildRequires:
Requires: pf9-dummy
Requires: pf9-resmgr
Requires: pf9-bbmaster
Requires: pf9-clarity
Requires: pf9-hostagent-tarball
Requires: pf9-ostackhost-wrapper
Requires: pf9-authproxy

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
%config /etc/rabbitmq/rabbitmq.config
