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


PF9_VERSION ?= 1.3.0
BUILD_NUMBER ?= 0
RPM_DIR := $(BUILD_DIR)/rpmbuild

# These additional modules need to be setup in order for our tests to run
TEST_SETUP_DEPS = ${PROD_SETUP_DEPS} ${SRC_ROOT}/bbone/bbslave ${PF9APP_DIR}
TEST_VENV = ${BUILD_DIR}/test_venv
TEST_VENV_DEVELOP_CMD=${TEST_VENV}/bin/python setup.py develop

BBMASTER_SRC_STAGE = ${BUILD_DIR}/srcstage/pf9-bbmaster-${PF9_VERSION}
BBMASTER_SRC_TARBALL = ${BUILD_DIR}/pf9-bbmaster-${PF9_VERSION}.tgz
PF9_OPT_DIR = ${BBMASTER_SRC_STAGE}/opt/pf9
PROD_VENV = ${PF9_OPT_DIR}/bbmaster
# These are additional modules needed to setup for production purposes
PROD_SETUP_DEPS = ${BBLIBCOMMON_DIR} ${CONFIGUTILS_DIR} ${PF9CERT_DIR}
PROD_VENV_INSTALL_CMD=${PROD_VENV}/bin/python setup.py install
name = pf9-bbmaster
desc = "Platform9 bbmaster service"
arch = "noarch"
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

PY_VERSION=py3

${BUILD_DIR}:
	mkdir -p $@

${VENV}: ${BUILD_DIR}
	mkdir -p $@
	$(SRC_ROOT)/build-venv.sh ${VENV} ${PY_VERSION}
	${VENV}/bin/pip install --upgrade pip setuptools
	${VENV}/bin/pip install six==1.12.0

${BBMASTER_SRC_STAGE}: pre-reqs
	mkdir -p ${BBMASTER_SRC_STAGE}/etc/pf9
	mkdir -p ${BBMASTER_SRC_STAGE}/usr/lib/systemd/system/
	mkdir -p ${BUILD_DIR}/rpmbuild
	mkdir -p ${BBMASTER_SRC_STAGE}/var/log/pf9
	cp ${BBMASTER_DIR}/etc/bbmaster.conf ${BBMASTER_SRC_STAGE}/etc/pf9
	cp ${BBMASTER_DIR}/config.py ${BBMASTER_SRC_STAGE}/etc/pf9/bbmaster_config.py
	mkdir -p ${PF9_OPT_DIR}/du-customize
	cp ${BBMASTER_DIR}/support/60-customize-bbmaster ${PF9_OPT_DIR}/du-customize
	mkdir -p ${PF9_OPT_DIR}/support
	cp ${BBMASTER_DIR}/pf9-bbmaster.service ${BBMASTER_SRC_STAGE}/usr/lib/systemd/system/pf9-bbmaster.service

${BBMASTER_SRC_TARBALL}: ${BBMASTER_SRC_STAGE}
	cd ${BUILD_DIR}/srcstage && \
	tar -czf ${BBMASTER_SRC_TARBALL} *

rpm: ${BBMASTER_SRC_TARBALL}
	echo "RPM build goes here"
	
	fpm -t rpm -s dir -n ${name} \
	--license "Commercial" \
        --description ${desc} \
        --package ${package} \
        --architecture ${arch} \
        --url "http://www.platform9.com" \
        --vendor Platform9 \
	--version ${PF9_VERSION} \
	--iteration ${BUILD_NUMBER}.${GITHASH} \
        --provides ${name} \
        -C ${BBMASTER_SRC_STAGE} .

	${SRC_ROOT}/sign_packages.sh ${RPM_DIR}/pf9-bbmaster*.rpm

pre-reqs : ${VENV}
	for pkg in ${SETUP_DEPS}; do \
		cd $${pkg} && \
		${VENV_CMD};\
	done
	cd ${BBMASTER_DIR} && \
	${VENV_CMD}

unit-test-setup: pre-reqs
	# Setup up nose and coverage in addition to pre-reqs
	source ${TEST_VENV}/bin/activate && \
	pip install nose && \
	pip install coverage

unit-test: unit-test-setup
	cd ${BBMASTER_DIR} && \
	PF9_COMMS_VERSION=1.0.0-1.2 PF9_COMMS_FILENAME=pf9-comms-1.0.0-1.2.rpm \
	PF9_MUSTER_VERSION=1.0.0-1.2 PF9_MUSTER_FILENAME=pf9-muster-1.0.0-1.2.rpm \
	${TEST_VENV}/bin/nosetests --with-coverage --cover-html --cover-html-dir=${BUILD_DIR}/coverage \
			--cover-package=bbmaster --cover-package=bbcommon --verbosity=2 --with-xunit \
			--xunit-file=${BUILD_DIR}/test_output.xml --exclude=load_test_app bbmaster/tests/test_master.py
	cd ${BBMASTER_DIR} && \
	${TEST_VENV}/bin/nosetests --with-coverage --cover-html --cover-html-dir=${BUILD_DIR}/coverage \
			--cover-package=bbmaster --cover-package=bbcommon --verbosity=2 --with-xunit \
			--xunit-file=${BUILD_DIR}/test_output.xml --exclude=load_test_app bbmaster/tests/test_controller.py
	cd ${BUILD_DIR}/coverage && \
	zip -q ${COVERAGE_ZIP} *

clean:
	rm -rf $(BUILD_DIR)
	rm -rf ${COVERAGE_ZIP}
