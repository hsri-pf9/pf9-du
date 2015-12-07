%define dl_mirror %{?mirror_url}%{!?mirror_url:http://http.debian.net/debian/pool/main/d/dpkg-sig}

Name:		dpkg-sig
Version:	0.13.1+nmu2
Release:	1%{?dist}
Summary:	create and verify signatures on .deb-files

Group:		Packaging
License:	GPL
URL:		%{dl_mirror}
Source0:	%{dl_mirror}/dpkg-sig_%{version}.tar.gz

Requires:	gnupg perl perl(Config::File) perl(Digest::MD5)
BuildArch:	noarch

%description
dpkg-sig is a low-level tool for creation and verification of signature on Debian binary packages (.deb-files).

%prep
%setup -n dpkg-sig-%{version}

%install
mkdir -p %{buildroot}/%{_bindir}
%{__install} -m 0755 dpkg-sig %{buildroot}/%{_bindir}

%files
%{_bindir}/dpkg-sig

%changelog
* Tue Dec 01 2015 Patrick McIlroy <patrick@platform9.com>
- Initial Package
