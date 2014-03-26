#! vim noexpandtab
# Copyright (C) 2013 Platform 9 Systems, Inc.
#

include ../../../common-defs.mk

PARENT_DIR := $(abspath $(SRC_ROOT)/..)

SRC_DIR := $(SRC_ROOT)/bbone/bbmaster
BUILD_DIR := $(BUILD_ROOT)/bbmaster

BBMASTER_DIR :=$(SRC_DIR)
PF9APP_DIR :=$(SRC_ROOT)/bbone/pf9app
BBLIBCOMMON_DIR :=$(SRC_ROOT)/bbone/lib
CONFIGUTILS_DIR :=$(SRC_ROOT)/lib/configutils
#Hack
#Putting pf9cert with bbmaster rpm for now. This needs to be fixed later
PF9CERT_DIR := $(SRC_ROOT)/lib/pf9cert


VERSION ?= 1.0.0
BBMASTER_RPM :=$(BUILD_DIR)/pf9-bbmaster-$(VERSION).rpm
RPM_DIR := $(BUILD_DIR)/rpmbuild
BBMASTER_SRC_RPM := $(RPM_DIR)/pf9-bbmaster-$(VERSION)-1.src.rpm
MOCK = /usr/bin/mock -r epel-6-x86_64

# These additional modules need to be setup in order for our tests to run
TEST_SETUP_DEPS = ${PROD_SETUP_DEPS} ${SRC_ROOT}/bbone/bbslave ${PF9APP_DIR}
TEST_VENV = ${BUILD_DIR}/test_venv
TEST_VENV_DEVELOP_CMD=${TEST_VENV}/bin/python setup.py develop

BBMASTER_SRC_STAGE = ${BUILD_DIR}/srcstage/pf9-bbmaster-${VERSION}
BBMASTER_SRC_TARBALL = ${BUILD_DIR}/pf9-bbmaster-${VERSION}.tgz
PF9_OPT_DIR = ${BBMASTER_SRC_STAGE}/opt/pf9
PROD_VENV = ${PF9_OPT_DIR}/bbmaster
# These are additional modules needed to setup for production purposes
PROD_SETUP_DEPS = ${BBLIBCOMMON_DIR} ${CONFIGUTILS_DIR} ${PF9CERT_DIR}
PROD_VENV_INSTALL_CMD=${PROD_VENV}/bin/python setup.py install

ifeq ($(MAKECMDGOALS),rpm)
	VENV=${PROD_VENV}
	SETUP_DEPS=${PROD_SETUP_DEPS}
	VENV_CMD=${PROD_VENV_INSTALL_CMD}
else
	VENV=${TEST_VENV}
	SETUP_DEPS=${TEST_SETUP_DEPS}
	VENV_CMD=${TEST_VENV_DEVELOP_CMD}
endif

#TODO: Coverage zip should probably be done as part of teamcity build steps.
COVERAGE_ZIP = ${SRC_ROOT}/coverage.zip

${BUILD_DIR}:
	mkdir -p $@

${VENV}: ${BUILD_DIR}
	mkdir -p $@
	virtualenv ${VENV}

${BBMASTER_SRC_STAGE}: pre-reqs
	mkdir -p ${BBMASTER_SRC_STAGE}/etc/pf9
	cp ${BBMASTER_DIR}/etc/bbmaster.conf ${BBMASTER_SRC_STAGE}/etc/pf9
	cp ${BBMASTER_DIR}/config.py ${BBMASTER_SRC_STAGE}/etc/pf9/bbmaster_config.py
	cp -r ${BBMASTER_DIR}/etc/init.d ${BBMASTER_SRC_STAGE}/etc
	mkdir -p ${PF9_OPT_DIR}/du-customize
	cp ${BBMASTER_DIR}/support/60-customize-bbmaster ${PF9_OPT_DIR}/du-customize
	cp ${BBMASTER_DIR}/support/generate-certs ${PF9_OPT_DIR}/du-customize
	cp ${BBMASTER_DIR}/support/05-generate-certs ${PF9_OPT_DIR}/du-customize

${BBMASTER_SRC_TARBALL}: ${BBMASTER_SRC_STAGE}
	cd ${BUILD_DIR}/srcstage;\
	tar -czf ${BBMASTER_SRC_TARBALL} *

${BBMASTER_RPM}: ${BBMASTER_SRC_TARBALL}
	echo "RPM build goes here"
	${MOCK} --buildsrpm --sources ${BUILD_DIR} --spec bbmaster-rpm.spec --resultdir ${RPM_DIR}
	${MOCK} --rebuild --resultdir ${RPM_DIR} ${BBMASTER_SRC_RPM}

pre-reqs : ${VENV}
	for pkg in ${SETUP_DEPS}; do \
		cd $${pkg};\
		${VENV_CMD};\
		done;\
	cd ${BBMASTER_DIR};\
	${VENV_CMD};

unit-test-setup: pre-reqs
	# Setup up nose and coverage in addition to pre-reqs
	source ${TEST_VENV}/bin/activate;\
	pip install nose;\
	pip install coverage;\
	deactivate

unit-test: unit-test-setup
	cd ${BBMASTER_DIR};\
	${TEST_VENV}/bin/nosetests --with-coverage --cover-html --cover-html-dir=${BUILD_DIR}/coverage \
			--cover-package=bbmaster --cover-package=bbcommon --verbosity=2 --with-xunit \
			--xunit-file=${BUILD_DIR}/test_output.xml --exclude=load_test_app bbmaster/tests/test_master.py; \
	${TEST_VENV}/bin/nosetests --with-coverage --cover-html --cover-html-dir=${BUILD_DIR}/coverage \
			--cover-package=bbmaster --cover-package=bbcommon --verbosity=2 --with-xunit \
			--xunit-file=${BUILD_DIR}/test_output.xml --exclude=load_test_app bbmaster/tests/test_controller.py; \
	cd ${BUILD_DIR}/coverage;\
	zip -q ${COVERAGE_ZIP} *;

rpm: ${BBMASTER_RPM}


clean:
	rm -rf $(BUILD_DIR)
	rm -rf ${COVERAGE_ZIP}
