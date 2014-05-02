#! vim noexpandtab
# Copyright (C) 2013 Platform 9 Systems, Inc.
#
# Usage: make hostagent-tarball
#
# CentOS 6.4 build environment requirements:
#
# RPMs: make gcc git
# The user running make must have sudo (with no password required) privilege.

include ../../../common-defs.mk

PARENT_DIR := $(abspath $(SRC_ROOT)/..)

MYSELF := $(shell whoami)
SRC_DIR := $(SRC_ROOT)/bbone/bbslave
BUILD_DIR := $(BUILD_ROOT)/hostagent
RPMBUILD_DIR := $(BUILD_DIR)/rpmbuild

VERSION ?= 1.0.0
HOST_IP ?= 10.1.10.254

HOSTAGENT_TARBALL_SRCDIR := $(BUILD_DIR)/hostagent-tarball-src

OPT_PF9_DIR := $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9
VENV_DIR := $(OPT_PF9_DIR)/hostagent

HOSTAGENT_TARBALL_EXPANDEDDIR := $(BUILD_DIR)/hostagent-tarball-expanded
HOSTAGENT_TARBALL := $(BUILD_DIR)/pf9-hostagent.tar.gz
RPM_DIR := $(BUILD_DIR)/rpmbuild
MOCK = /usr/bin/mock -r epel-6-x86_64

HOSTAGENT_ROOT := $(RPM_TAR_ROOT)/rpmsrc

VENV_INSTALL_CMD=$(VENV_DIR)/bin/python setup.py install

BBSLAVE_DIR :=$(SRC_DIR)
PF9APP_DIR :=$(SRC_ROOT)/bbone/pf9app
BBLIBCOMMON_DIR :=$(SRC_ROOT)/bbone/lib
CONFIGUTILS_DIR :=$(SRC_ROOT)/lib/configutils

$(BUILD_DIR):
	mkdir -p $@

$(OPT_PF9_DIR):
	mkdir -p $@

# Site packages required: bbslave needs 'yum' which is not available on PyPi
$(VENV_DIR): | $(OPT_PF9_DIR) $(BUILD_DIR)
	virtualenv --system-site-packages $@

$(HOSTAGENT_TARBALL_EXPANDEDDIR):
	rm -fr $@
	mkdir -p $@

$(HOSTAGENT_TARBALL_SRCDIR):
	rm -fr $@
	mkdir -p $@
	cp -r $(BBSLAVE_DIR)/etc $@/

install-bbslave: | $(BUILD_DIR) $(VENV_DIR)
	cd $(CONFIGUTILS_DIR);\
	$(VENV_INSTALL_CMD)
	cd $(PF9APP_DIR);\
	$(VENV_INSTALL_CMD)
	cd $(BBLIBCOMMON_DIR);\
	$(VENV_INSTALL_CMD)
	cd $(BBSLAVE_DIR);\
	$(VENV_INSTALL_CMD)

$(HOSTAGENT_TARBALL): | $(HOSTAGENT_TARBALL_SRCDIR) install-bbslave
	cp $(SRC_DIR)/support/hostagent.spec $(HOSTAGENT_TARBALL_SRCDIR)
	cp $(SRC_DIR)/support/hostagent-rpmbuild.sh $(HOSTAGENT_TARBALL_SRCDIR)
	cp $(SRC_DIR)/scripts/pf9-hostagent $(VENV_DIR)/bin
	cd $(HOSTAGENT_TARBALL_SRCDIR);\
	tar -czf $(HOSTAGENT_TARBALL) *

hostagent-expand-tarball: | $(HOSTAGENT_TARBALL_EXPANDEDDIR) $(HOSTAGENT_TARBALL)
	tar -xzf $(HOSTAGENT_TARBALL) -C $(HOSTAGENT_TARBALL_EXPANDEDDIR)

# The creation of RPM will be at a time when we won't have access to
# the make system, so the hostagent-rpmbuild should be self contained
# and needs only the expanded tar file to exist and optionally pass in as a parameter
# - Expanded directory of tarball
# - (Optional) Version for the rpm
# - (Optional) Ip/DNS name of the service
hostagent-rpm: hostagent-expand-tarball
	$(HOSTAGENT_TARBALL_EXPANDEDDIR)/hostagent-rpmbuild.sh $(RPMBUILD_DIR) $(HOSTAGENT_TARBALL_EXPANDEDDIR) $(VERSION) $(HOST_IP)

hostagent-tarball: $(HOSTAGENT_TARBALL)

hostagent-tarball-rpm: hostagent-tarball
	cp ${SRC_DIR}/support/45-customize-hostagent-rpm ${BUILD_DIR}
	sed -e "s/__GITHASH__/$(shell git rev-parse --short HEAD)/" hostagent-tarball-rpm.spec > ${BUILD_DIR}/hostagent-tarball-rpm.spec
	${MOCK} --buildsrpm --sources ${BUILD_DIR} --spec ${BUILD_DIR}/hostagent-tarball-rpm.spec --resultdir ${RPM_DIR}
	mv ${RPM_DIR}/*.src.rpm ${BUILD_DIR}
	${MOCK} --rebuild --resultdir ${RPM_DIR} ${BUILD_DIR}/*.src.rpm
	rm -f ${BUILD_DIR}/*.src.rpm

# These additional modules need to be setup in order for our tests to run
TEST_SETUP_DEPS = ${BBLIBCOMMON_DIR} ${SRC_ROOT}/bbone/bbmaster ${PF9APP_DIR} ${CONFIGUTILS_DIR}
TEST_VENV = ${BUILD_DIR}/hostagent_venv
TEST_VENV_DEVELOP_CMD=${TEST_VENV}/bin/python setup.py develop
COVERAGE_ZIP = ${SRC_ROOT}/coverage.zip
DISTUTILS_DEBUG = 1

${TEST_VENV}: ${BUILD_DIR}
	virtualenv ${TEST_VENV}

pre-reqs : ${TEST_VENV}
	for pkg in ${TEST_SETUP_DEPS}; do \
		cd $${pkg};\
		${TEST_VENV_DEVELOP_CMD};\
	done;\
	cd ${BBSLAVE_DIR};\
	${TEST_VENV_DEVELOP_CMD};

unit-test-setup: pre-reqs
	# Setup up nose and coverage in addition to pre-reqs
	source ${TEST_VENV}/bin/activate;\
	pip install nose;\
	pip install coverage;\
	deactivate

unit-test: unit-test-setup
	cd ${BBSLAVE_DIR};\
	${TEST_VENV}/bin/nosetests --with-coverage --cover-html --cover-html-dir=${BUILD_DIR}/coverage \
			--cover-package=bbslave --verbosity=2 --with-xunit --xunit-file=${BUILD_DIR}/test_output.xml test/test_slave.py;\
	cd ${BUILD_DIR}/coverage;\
	zip -q ${COVERAGE_ZIP} *;


clean:
	rm -rf $(BUILD_DIR)
	rm -rf ${COVERAGE_ZIP}
