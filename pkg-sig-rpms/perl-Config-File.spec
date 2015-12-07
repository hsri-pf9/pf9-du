%define real_name Config-File
%define perl_vendorlib %(eval "`%{__perl} -V:installvendorlib`"; echo $installvendorlib)
%define dl_mirror %{?mirror_url}%{!?mirror_url:http://search.cpan.org/CPAN/authors/id/G/GW/GWOLF}

Name:		perl-Config-File
Version:	1.50
Release:	1%{?dist}
Summary:	Parse a simple configuration file

Group:		Applications/CPAN
License:	Artistic/GPL
URL:		%{dl_mirror}
Source0:	%{dl_mirror}/Config-File-1.50.tar.gz

BuildRequires:	perl perl(Test::Pod) perl(Test::Pod::Coverage) perl(Module::Build)
BuildArch:  noarch

%description
Config::File - Parse a simple configuration file

%prep
%setup -n %{real_name}-%{version}

%build
%{__perl} Makefile.PL INSTALLDIRS="vendor" PREFIX="%{buildroot}%{_prefix}"
%{__make} %{?_smp_mflags}

%install
%{__make} pure_install
find %{buildroot} -name .packlist -exec %{__rm} {} \;

%files
%defattr(-, root, root, 0755)
%doc CHANGES MANIFEST README
%doc %{_mandir}/man3/Config::File.3pm.gz
%dir %{perl_vendorlib}/Config/
%{perl_vendorlib}/Config/File.pm

%changelog
* Tue Dec 01 2015 Patrick McIlroy <patrick@platform9.com>
- Initial Package
