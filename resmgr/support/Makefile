#! vim noexpandtab
# Copyright (C) 2013 Platform 9 Systems, Inc.
#

include ../../common-defs.mk

PARENT_DIR := $(abspath $(SRC_ROOT)/..)

SRC_DIR := $(SRC_ROOT)/resmgr
BUILD_DIR := $(BUILD_ROOT)/resmgr

RESMGR_DIR :=$(SRC_DIR)
BBLIBCOMMON_DIR :=$(SRC_ROOT)/bbone/lib
CONFIGUTILS_DIR :=$(SRC_ROOT)/lib/configutils
NOTIFIER_DIR :=$(SRC_ROOT)/lib/notifier
RABBIT_MGMT_DIR :=$(SRC_ROOT)/lib/rabbit

FIRKINIZE = $(PARENT_DIR)/firkinize

PF9_VERSION ?= 1.3.0
BUILD_NUMBER ?= 0
RPM_DIR := $(BUILD_DIR)/rpmbuild
MOCK = /usr/bin/mock -r epel-7-x86_64

RESMGR_SRC_STAGE = ${BUILD_DIR}/srcstage/pf9-resmgr-${PF9_VERSION}
RESMGR_SRC_TARBALL = ${BUILD_DIR}/pf9-resmgr-${PF9_VERSION}.tgz
PF9_OPT_DIR = ${RESMGR_SRC_STAGE}/opt/pf9
CONSTRAINTS_FILE=${SRC_DIR}/upper-constraints.txt
PROD_VENV = ${PF9_OPT_DIR}/resmgr
# These are additional modules needed to setup for production purposes
PROD_SETUP_DEPS = ${BBLIBCOMMON_DIR} ${CONFIGUTILS_DIR} ${NOTIFIER_DIR} ${RABBIT_MGMT_DIR} ${FIRKINIZE}
PROD_VENV_INSTALL_CMD=${PROD_VENV}/bin/python ${PROD_VENV}/bin/pip install -c${CONSTRAINTS_FILE}
# These additional modules need to be setup in order for our tests to run
TEST_SETUP_DEPS = ${PROD_SETUP_DEPS}
TEST_VENV = ${BUILD_DIR}/test_venv
TEST_VENV_DEVELOP_CMD=${TEST_VENV}/bin/python ${TEST_VENV}/bin/pip install -c${CONSTRAINTS_FILE} -e

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

PY_VERSION=py3

${VENV}: ${BUILD_DIR}
	mkdir -p $@
	$(SRC_ROOT)/build-venv.sh ${VENV} ${PY_VERSION}

${RESMGR_SRC_STAGE}: pre-reqs
	mkdir -p ${RESMGR_SRC_STAGE}/var/log/pf9
	mkdir -p ${RESMGR_SRC_STAGE}/etc/pf9
	mkdir -p ${RESMGR_SRC_STAGE}/etc/pf9/resmgr_roles
	mkdir -p ${RESMGR_SRC_STAGE}/etc/pf9/resmgr_svc_configs
	cp ${RESMGR_DIR}/etc/pf9/resmgr.conf ${RESMGR_SRC_STAGE}/etc/pf9/
	cp ${RESMGR_DIR}/etc/pf9/resmgr_config.py ${RESMGR_SRC_STAGE}/etc/pf9/
	cp ${RESMGR_DIR}/etc/pf9/resmgr-paste.ini ${RESMGR_SRC_STAGE}/etc/pf9/
	cp ${RESMGR_DIR}/pf9-resmgr.service ${RESMGR_SRC_STAGE}/pf9-resmgr.service

	mkdir -p ${VENV}/bin
	cp ${RESMGR_DIR}/bin/db_sync.py ${VENV}/bin
	cp ${RESMGR_DIR}/bin/resmgr-daemon.py ${VENV}/bin/

	mkdir -p ${PF9_OPT_DIR}/du-customize
	cp ${RESMGR_DIR}/support/50-customize-resmgr ${PF9_OPT_DIR}/du-customize

${RESMGR_SRC_TARBALL}: ${RESMGR_SRC_STAGE}
	cd ${BUILD_DIR}/srcstage && \
	tar -czf ${RESMGR_SRC_TARBALL} *

rpm: ${RESMGR_SRC_TARBALL}
	sed -e "s/__BUILDNUM__/${BUILD_NUMBER}/" -e "s/__VERSION__/${PF9_VERSION}/" \
	    -e "s/__GITHASH__/$(shell git rev-parse --short HEAD)/" resmgr-rpm.spec \
	    > ${BUILD_DIR}/resmgr-rpm.spec
	${MOCK} --buildsrpm --sources ${BUILD_DIR} --spec ${BUILD_DIR}/resmgr-rpm.spec --resultdir ${RPM_DIR}
	mv ${RPM_DIR}/*.src.rpm ${BUILD_DIR}
	${MOCK} --rebuild --resultdir ${RPM_DIR} ${BUILD_DIR}/*.src.rpm
	${SRC_ROOT}/sign_packages.sh ${RPM_DIR}/pf9-resmgr*.rpm
	rm -f ${BUILD_DIR}/*.src.rpm

pre-reqs: ${VENV}
	${VENV_CMD} ${SETUP_DEPS} ${RESMGR_DIR}

unit-test-setup: pre-reqs
	# Setup up nose and coverage in addition to pre-reqs
	source ${TEST_VENV}/bin/activate && \
	pip install --upgrade pip && \
	pip install nose mock coverage httpretty pylint && \
	deactivate

unit-test: unit-test-setup
	cd ${RESMGR_DIR} && \
	${TEST_VENV}/bin/nosetests -s --with-coverage --cover-html --cover-html-dir=${BUILD_DIR}/coverage \
			--cover-package=resmgr --cover-package=bbcommon --verbosity=2 --with-xunit \
			--xunit-file=${BUILD_DIR}/test_output.xml --exclude=load_test_app && \
	cd ${BUILD_DIR}/coverage && \
	zip -q ${COVERAGE_ZIP} *

clean:
	rm -rf $(BUILD_DIR)
	rm -rf ${COVERAGE_ZIP}
	rm -rf $(SRC_DIR)/build/ $(SRC_DIR)/dist/ $(SRC_DIR)/resmgr.egg-info/
