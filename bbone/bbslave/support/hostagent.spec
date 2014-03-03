Name:           pf9-hostagent
Version:        %{_version}
Release:        1
Summary:        Platform 9 host agent

License:        Commercial
URL:            http://www.platform9.net

AutoReqProv:    no

Provides:       pf9-hostagent
Requires:       sudo

# Hack to suppress PR IAAS-110
%define __prelink_undo_cmd %{nil}

%description
Platform 9 host agent

%prep

%build

%install
SRC_DIR=%_src_dir

rm -fr $RPM_BUILD_ROOT
mkdir -p $RPM_BUILD_ROOT
cp -r $SRC_DIR/* $RPM_BUILD_ROOT/

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
/opt/pf9
/etc/init.d/pf9-hostagent
/etc/pf9

%post
chkconfig --add pf9-hostagent
service pf9-hostagent start
%preun
# $1==0: remove the last version of the package
# $1==1: install the first time
# $1>=2: upgrade
if [ "$1" = 0 ]; then
  service pf9-hostagent stop > /dev/null
  chkconfig --del pf9-hostagent
fi

%postun

%changelog
