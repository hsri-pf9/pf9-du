Name:		debsig-verify
Version:	0.8
Release:	1%{?dist}
Summary:	Debian Package Signature Verification Tool

Group:		Packaging
License:	GPL
URL:		http://http.debian.net/debian/pool/main/d/debsig-verify/
Source0:	http://http.debian.net/debian/pool/main/d/debsig-verify/debsig-verify_%{version}.tar.gz
Patch0:		pf9-xmltok-to-expat.patch

Requires:	gnupg expat
BuildRequires:  expat-devel
BuildArch:	%{_arch}

%description
This tool inspects and verifies package signatures based on predetermined policies.

%prep
%setup -n debsig-verify-%{version}
%patch0 -p1

%install
%{__make} DESTDIR="%{buildroot}" install

%files
%{_bindir}/debsig-verify
%{_sysconfdir}/debsig/policies
%{_datadir}/debsig/keyrings
%{_mandir}/man1/debsig-verify.1.gz

%changelog
* Tue Dec 01 2015 Patrick McIlroy <patrick@platform9.com>
- Initial Package
