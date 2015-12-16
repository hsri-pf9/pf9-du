Name:		debsigs
Version:	0.1.18
Release:	1%{?dist}
Summary:	toolset for applying cryptographic signatures to Debian packages

Group:		Packaging
License:	GPL
URL:		http://http.debian.net/debian/pool/main/d/debsigs/
Source0:	http://http.debian.net/debian/pool/main/d/debsigs/debsigs_%{version}.tar.xz

Requires:	gnupg perl
BuildRequires: perl perl(Module::Build)
BuildArch:	noarch

%description
debsigs is a package that allows GPG signatures to be embedded inside Debian packages.  These signatures can later be verified by package retrieval and installation tools to ensure the authenticity of the contents of the package.

%prep
%setup -n debsigs-%{version}

%install
%{__perl} Makefile.PL INSTALLDIRS="vendor" PREFIX="%{buildroot}%{_prefix}"
%{__make} %{?_smp_mflags} pure_install

%files
%{_bindir}/debsigs-signchanges
%{_bindir}/debsigs-installer
%{_bindir}/debsigs
%{_bindir}/debsigs-autosign
%{_mandir}/man1/debsigs.1.gz
%{_mandir}/man1/debsigs-signchanges.1.gz
%{_mandir}/man1/debsigs-installer.1.gz
%{_mandir}/man1/debsigs-autosign.1.gz
%{_mandir}/man3/Debian::debsigs::debsigsmain.3pm.gz
%{perl_vendorarch}/auto/Debian/debsigs/debsigs/.packlist
%{perl_vendorlib}/auto/Debian/debsigs/debsigsmain/autosplit.ix
%{perl_vendorlib}/Debian/debsigs/gpg.pm
%{perl_vendorlib}/Debian/debsigs/forktools.pm
%{perl_vendorlib}/Debian/debsigs/debsigsmain.pm
%{perl_vendorlib}/Debian/debsigs/arf.pm

%changelog
* Wed Dec 16 2015 Patrick McIlroy <patrick@platform9.com>
- debsigs 0.1.18
* Tue Dec 01 2015 Patrick McIlroy <patrick@platform9.com>
- Initial Package
