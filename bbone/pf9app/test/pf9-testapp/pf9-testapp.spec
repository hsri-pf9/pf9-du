Name:           pf9-testapp
Version:        1.0.0
Release:        1
Summary:        Platform 9 test app

License:        Commercial
URL:            http://www.platform9.net

AutoReqProv:    no

Provides:       pf9testapp
Provides:       pf9app
Requires:       sudo

BuildArch:      noarch
Group:          pf9apps

Source0:        pf9-testapp.conf
Source1:        pf9-testapp
Source2:        pf9-testapp.configscript
Source3:        pf9-testapp.initd
Source4:        __init__.py
Source5:        configutils.py

%define _unpackaged_files_terminate_build 0

%description
Platform 9 test app

%prep

%build

%install
rm -rf ${RPM_BUILD_ROOT}
mkdir ${RPM_BUILD_ROOT}

mkdir -p ${RPM_BUILD_ROOT}/opt/pf9/etc/pf9-testapp
mkdir -p ${RPM_BUILD_ROOT}/opt/pf9/pf9-testapp
mkdir -p ${RPM_BUILD_ROOT}/etc/init.d

cp %{SOURCE0} ${RPM_BUILD_ROOT}/opt/pf9/etc/pf9-testapp/pf9-testapp.conf
cp %{SOURCE1} ${RPM_BUILD_ROOT}/opt/pf9/pf9-testapp/pf9-testapp
cp %{SOURCE2} ${RPM_BUILD_ROOT}/opt/pf9/pf9-testapp/config
cp %{SOURCE3} ${RPM_BUILD_ROOT}/etc/init.d/pf9-testapp
cp %{SOURCE4} ${RPM_BUILD_ROOT}/opt/pf9/pf9-testapp/__init__.py
cp %{SOURCE5} ${RPM_BUILD_ROOT}/opt/pf9/pf9-testapp/configutils.py

%clean
rm -rf ${RPM_BUILD_ROOT}


%files
%attr(755, -, -)/opt/pf9/pf9-testapp/pf9-testapp
%attr(755, -, -)/opt/pf9/pf9-testapp/config
/opt/pf9/pf9-testapp/__init__.py
/opt/pf9/pf9-testapp/configutils.py
%config(noreplace)/opt/pf9/etc/pf9-testapp/pf9-testapp.conf
%attr(755, -, -)/etc/init.d/pf9-testapp



%post
/sbin/chkconfig --add pf9-testapp

%preun
if [ $1 -eq 0 ] ; then
    /sbin/service pf9-testapp stop >/dev/null 2>&1
    /sbin/chkconfig --del pf9-testapp
fi

# Restart daemon on upgrade
%postun
if [ $1 -ge 1 ] ; then
    /sbin/service pf9-testapp condrestart > /dev/null 2>&1 || :
fi

%changelog
