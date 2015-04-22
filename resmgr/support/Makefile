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

VERSION ?= 1.0.0
BUILD_NUMBER ?= 0
RPM_DIR := $(BUILD_DIR)/rpmbuild
MOCK = /usr/bin/mock -r epel-6-x86_64

RESMGR_SRC_STAGE = ${BUILD_DIR}/srcstage/pf9-resmgr-${VERSION}
RESMGR_SRC_TARBALL = ${BUILD_DIR}/pf9-resmgr-${VERSION}.tgz
PF9_OPT_DIR = ${RESMGR_SRC_STAGE}/opt/pf9
PROD_VENV = ${PF9_OPT_DIR}/resmgr
# These are additional modules needed to setup for production purposes
PROD_SETUP_DEPS = ${BBLIBCOMMON_DIR} ${CONFIGUTILS_DIR} ${NOTIFIER_DIR} ${RABBIT_MGMT_DIR}
PROD_VENV_INSTALL_CMD=${PROD_VENV}/bin/python setup.py install
# These additional modules need to be setup in order for our tests to run
TEST_SETUP_DEPS = ${PROD_SETUP_DEPS}
TEST_VENV = ${BUILD_DIR}/test_venv
TEST_VENV_DEVELOP_CMD=${TEST_VENV}/bin/python setup.py develop

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

${RESMGR_SRC_STAGE}: pre-reqs
	source ${VENV}/bin/activate && \
	pip install MySQL-python && \
	deactivate

	mkdir -p ${RESMGR_SRC_STAGE}/var/log/pf9
	mkdir -p ${RESMGR_SRC_STAGE}/etc/pf9
	mkdir -p ${RESMGR_SRC_STAGE}/etc/pf9/resmgr_roles
	cp ${RESMGR_DIR}/etc/pf9/resmgr.conf ${RESMGR_SRC_STAGE}/etc/pf9/
	cp ${RESMGR_DIR}/etc/pf9/resmgr_config.py ${RESMGR_SRC_STAGE}/etc/pf9/
	cp ${RESMGR_DIR}/etc/pf9/resmgr-paste.ini ${RESMGR_SRC_STAGE}/etc/pf9/

	mkdir -p ${VENV}/bin
	cp ${RESMGR_DIR}/bin/db_sync.py ${VENV}/bin
	cp ${RESMGR_DIR}/bin/resmgr-daemon.py ${VENV}/bin/

	mkdir -p ${RESMGR_SRC_STAGE}/etc/rc.d/init.d
	cp -r ${RESMGR_DIR}/etc/init.d/pf9-resmgr ${RESMGR_SRC_STAGE}/etc/rc.d/init.d/

	mkdir -p ${PF9_OPT_DIR}/du-customize
	cp ${RESMGR_DIR}/support/50-customize-resmgr ${PF9_OPT_DIR}/du-customize

${RESMGR_SRC_TARBALL}: ${RESMGR_SRC_STAGE}
	cd ${BUILD_DIR}/srcstage && \
	tar -czf ${RESMGR_SRC_TARBALL} *

rpm: ${RESMGR_SRC_TARBALL}
	sed -e "s/__BUILDNUM__/${BUILD_NUMBER}/" -e "s/__VERSION__/${VERSION}/" \
	    -e "s/__GITHASH__/$(shell git rev-parse --short HEAD)/" resmgr-rpm.spec \
	    > ${BUILD_DIR}/resmgr-rpm.spec
	${MOCK} --buildsrpm --sources ${BUILD_DIR} --spec ${BUILD_DIR}/resmgr-rpm.spec --resultdir ${RPM_DIR}
	mv ${RPM_DIR}/*.src.rpm ${BUILD_DIR}
	${MOCK} --rebuild --resultdir ${RPM_DIR} ${BUILD_DIR}/*.src.rpm
	rm -f ${BUILD_DIR}/*.src.rpm

pre-reqs: ${VENV}
	for pkg in ${SETUP_DEPS}; do \
		cd $${pkg} && \
		${VENV_CMD}; \
	done
	cd ${RESMGR_DIR} && \
	${VENV_CMD}

	# the keystone client has to be installed with pip. Installing with setuptools exposes
	# https://bitbucket.org/pypa/setuptools/issue/73/typeerror-dist-must-be-a-distribution
	source ${VENV}/bin/activate &&  \
	pip install python-keystoneclient &&  \
	pip install Paste==1.7.5.1 && \
	pip install PasteDeploy && \
	deactivate


unit-test-setup: pre-reqs
	# Setup up nose and coverage in addition to pre-reqs
	source ${TEST_VENV}/bin/activate && \
	pip install nose && \
	pip install coverage && \
	pip install httpretty &&  \
	deactivate

unit-test: unit-test-setup
	cd ${RESMGR_DIR} && \
	${TEST_VENV}/bin/nosetests --with-coverage --cover-html --cover-html-dir=${BUILD_DIR}/coverage \
			--cover-package=resmgr --cover-package=bbcommon --verbosity=2 --with-xunit \
			--xunit-file=${BUILD_DIR}/test_output.xml --exclude=load_test_app && \
	cd ${BUILD_DIR}/coverage && \
	zip -q ${COVERAGE_ZIP} *

clean:
	rm -rf $(BUILD_DIR)
	rm -rf ${COVERAGE_ZIP}
	rm -rf $(SRC_DIR)/build/ $(SRC_DIR)/dist/ $(SRC_DIR)/resmgr.egg-info/
