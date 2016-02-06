#! vim noexpandtab
# Copyright (C) 2014 Platform 9 Systems, Inc.
#
# Usage: make hostagent-tarball
#
# CentOS 6.4 build environment requirements:
#
# RPMs: make gcc git
# The user running make must have sudo (with no password required) privilege.

include ../../../../common-defs.mk

BUILD_DIR := $(BUILD_ROOT)/hostagent/redhat
PYTHON_VERSION = 2.6

# This defines SRC_DIR, VENV_DIR, HOSTAGENT_TARBALL,
# HOSTAGENT_TARBALL_SRCDIR and SED_CMD
include ../common-hostagent-defs.mk

RPM_DIR := $(BUILD_DIR)/rpmbuild
MOCK = /usr/bin/mock -r epel-6-x86_64

$(HOSTAGENT_TARBALL): $(VENV_DIR)
	mkdir -p $(HOSTAGENT_TARBALL_SRCDIR)/etc/rc.d/init.d
	mkdir -p $(HOSTAGENT_TARBALL_SRCDIR)/etc/sudoers.d
	mkdir -p $(HOSTAGENT_TARBALL_SRCDIR)/var/opt/pf9
	mkdir -p $(HOSTAGENT_TARBALL_SRCDIR)/var/cache/pf9apps
	cp $(SRC_DIR)/support_scripts/redhat/* $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/support/
	cp $(SRC_DIR)/etc/init.d/pf9-hostagent-redhat $(HOSTAGENT_TARBALL_SRCDIR)/etc/rc.d/init.d/pf9-hostagent
	cp $(SRC_DIR)/etc/sudoers.d/pf9-hostagent-redhat $(HOSTAGENT_TARBALL_SRCDIR)/etc/sudoers.d/pf9-hostagent
	cp $(SRC_DIR)/support/redhat/hostagent.spec $(HOSTAGENT_TARBALL_SRCDIR)
	cp $(SRC_DIR)/support/redhat/hostagent-rpm-build.sh $(HOSTAGENT_TARBALL_SRCDIR)
	cp $(SRC_DIR)/scripts/pf9-yum $(VENV_DIR)/bin
	cd $(HOSTAGENT_TARBALL_SRCDIR) && \
	tar -czf $(HOSTAGENT_TARBALL) *

hostagent-tarball-rpm-redhat: $(HOSTAGENT_TARBALL)
	$(SED_CMD) ${SRC_DIR}/support/redhat/45-customize-hostagent-rpm > ${BUILD_DIR}/45-customize-hostagent-rpm
	chmod +x ${BUILD_DIR}/45-customize-hostagent-rpm
	$(SED_CMD) ${SRC_DIR}/support/redhat/47-customize-hostagent-ova > ${BUILD_DIR}/47-customize-hostagent-ova
	chmod +x ${BUILD_DIR}/47-customize-hostagent-ova
	$(SED_CMD) hostagent-tarball-rpm.spec > ${BUILD_DIR}/hostagent-tarball-rpm.spec
	${MOCK} --buildsrpm --sources ${BUILD_DIR} --spec ${BUILD_DIR}/hostagent-tarball-rpm.spec --resultdir ${RPM_DIR}
	mv ${RPM_DIR}/*.src.rpm ${BUILD_DIR}
	${MOCK} --rebuild --resultdir ${RPM_DIR} ${BUILD_DIR}/*.src.rpm
	rm -f ${BUILD_DIR}/*.src.rpm
	$(SRC_ROOT)/sign_packages.sh ${RPM_DIR}/RPMS/*/pf9-hostagent-tarball*.rpm

hostagent-tarball-rpm-redhat: TARGET_DISTRO = redhat

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
		cd $${pkg} && \
		${TEST_VENV_DEVELOP_CMD};\
	done
	cd ${SRC_DIR} && \
	${TEST_VENV_DEVELOP_CMD}

unit-test-setup: pre-reqs
	# Setup up nose and coverage in addition to pre-reqs
	source ${TEST_VENV}/bin/activate && \
	pip install nose && \
	pip install coverage

unit-test: unit-test-setup
	cd ${SRC_DIR} && \
	HOSTAGENT_HOST_ID_BASEDIR=${BUILD_DIR} ${TEST_VENV}/bin/nosetests --with-coverage --cover-html --cover-html-dir=${BUILD_DIR}/coverage \
			--cover-package=bbslave --verbosity=2 --with-xunit --xunit-file=${BUILD_DIR}/test_output.xml test/test_slave.py
	cd ${BUILD_DIR}/coverage && \
	zip -q ${COVERAGE_ZIP} *


clean:
	rm -rf $(BUILD_DIR)
	rm -rf ${COVERAGE_ZIP}
