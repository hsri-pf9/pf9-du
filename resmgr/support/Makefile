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

PF9_VERSION ?= 1.3.0
BUILD_NUMBER ?= 0
RPM_DIR := $(BUILD_DIR)/rpmbuild
name = pf9-resmgr
RESMGR_SRC_STAGE = ${BUILD_DIR}/srcstage/pf9-resmgr-${PF9_VERSION}
RESMGR_SRC_TARBALL = ${BUILD_DIR}/pf9-resmgr-${PF9_VERSION}.tgz
PF9_OPT_DIR = ${RESMGR_SRC_STAGE}/opt/pf9
CONSTRAINTS_FILE=${SRC_DIR}/upper-constraints.txt
PROD_VENV = ${PF9_OPT_DIR}/resmgr
# These are additional modules needed to setup for production purposes
PROD_SETUP_DEPS = ${BBLIBCOMMON_DIR} ${CONFIGUTILS_DIR} ${NOTIFIER_DIR} ${RABBIT_MGMT_DIR}
PROD_VENV_INSTALL_CMD_PIP=${PROD_VENV}/bin/pip install --upgrade pip==21.2.4;
PROD_VENV_INSTALL_CMD=${PROD_VENV_INSTALL_CMD_PIP} ${PROD_VENV}/bin/python ${PROD_VENV}/bin/pip install  -c${CONSTRAINTS_FILE}
# These additional modules need to be setup in order for our tests to run
TEST_SETUP_DEPS = ${PROD_SETUP_DEPS}
TEST_VENV = ${BUILD_DIR}/test_venv
TEST_VENV_DEVELOP_CMD_PIP=${TEST_VENV}/bin/pip install --upgrade pip==21.2.4; 
TEST_VENV_DEVELOP_CMD=${TEST_VENV_DEVELOP_CMD_PIP} ${TEST_VENV}/bin/python ${TEST_VENV}/bin/pip install -c${CONSTRAINTS_FILE} -e
desc = "Platform9 Resource Manager"
arch = noarch
GITHASH = $(shell git rev-parse --short HEAD)
package = ${RPM_DIR}/${name}-${PF9_VERSION}-${BUILD_NUMBER}.$(GITHASH).${arch}.rpm 

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
	mkdir -p ${RESMGR_SRC_STAGE}/usr/lib/systemd/system/
	mkdir -p ${BUILD_DIR}/rpmbuild
	cp ${RESMGR_DIR}/etc/pf9/resmgr.conf ${RESMGR_SRC_STAGE}/etc/pf9/
	cp ${RESMGR_DIR}/etc/pf9/resmgr_config.py ${RESMGR_SRC_STAGE}/etc/pf9/
	cp ${RESMGR_DIR}/etc/pf9/resmgr-paste.ini ${RESMGR_SRC_STAGE}/etc/pf9/
	cp ${RESMGR_DIR}/pf9-resmgr.service ${RESMGR_SRC_STAGE}/usr/lib/systemd/system/pf9-resmgr.service

	mkdir -p ${VENV}/bin
	cp ${RESMGR_DIR}/bin/db_sync.py ${VENV}/bin
	cp ${RESMGR_DIR}/bin/resmgr-daemon.py ${VENV}/bin/

	mkdir -p ${PF9_OPT_DIR}/du-customize
	cp ${RESMGR_DIR}/support/50-customize-resmgr ${PF9_OPT_DIR}/du-customize

${RESMGR_SRC_TARBALL}: ${RESMGR_SRC_STAGE}
	cd ${BUILD_DIR}/srcstage && \
	tar -czf ${RESMGR_SRC_TARBALL} *

rpm: ${RESMGR_SRC_TARBALL}
	fpm -t rpm -s dir -n ${name} \
	--license "Commercial" \
	--architecture ${arch} \
	--url "http://www.platform9.com" \
	--description ${desc} \
	--package ${package} \
	--after-install ${RESMGR_DIR}/support/after-install \
	--before-remove ${RESMGR_DIR}/support/before-remove \
	--vendor "Platform9" \
	--version ${PF9_VERSION} \
	--iteration ${BUILD_NUMBER}.${GITHASH} \
	--provides ${name} \
	-C ${RESMGR_SRC_STAGE} .

	${SRC_ROOT}/sign_packages.sh ${RPM_DIR}/pf9-resmgr*.rpm

pre-reqs: ${VENV}
	${VENV_CMD} ${SETUP_DEPS} ${RESMGR_DIR}

unit-test-setup: pre-reqs
	# Setup up nose and coverage in addition to pre-reqs
	source ${TEST_VENV}/bin/activate && \
	python -m pip install --upgrade pip==20.2.4 && \
	python -m pip install nose mock coverage httpretty pylint && \
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
