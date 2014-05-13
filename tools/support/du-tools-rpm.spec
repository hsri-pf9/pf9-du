Name:           pf9-du-tools
Version:        %{_version}
Release:        __BUILDNUM__.__GITHASH__
Summary:        Platform9 Deployment Unit Tools

License:        Commercial
URL:            http://www.platform9.net

AutoReqProv:    no

Provides:       pf9-du-tools

BuildArch:      noarch
Group:          pf9-du-tools

%description
Platform9 Deployment Unit Tools

%prep

%build

%install
SRC_DIR=%_src_dir  # pf9-du-tools
DEST_DU_TOOLS_DIR=${RPM_BUILD_ROOT}/opt/pf9/du-tools
DEST_DU_CTL_DIR=${DEST_DU_TOOLS_DIR}/du-ctl
mkdir -p ${DEST_DU_TOOLS_DIR}
mkdir -p ${DEST_DU_CTL_DIR}
cp ${SRC_DIR}/du_ctl/du_ctl ${DEST_DU_CTL_DIR}

%clean
rm -rf ${RPM_BUILD_ROOT}

%files
%defattr(-,root,root,-)
/opt/pf9/du-tools

%post

%preun

%postun

%changelog


