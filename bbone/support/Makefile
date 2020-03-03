#! vim noexpandtab
# Copyright (C) 2014 Platform 9 Systems, Inc.
#

include ../../common-defs.mk

SRC_DIR := $(SRC_ROOT)/bbone
BUILD_DIR := $(BUILD_ROOT)/bbone

BBMASTER_DIR :=$(SRC_ROOT)/bbone/bbmaster
BBSLAVE_DIR :=$(SRC_ROOT)/bbone/bbslave
PF9APP_DIR :=$(SRC_ROOT)/bbone/pf9app
BBLIBCOMMON_DIR :=$(SRC_ROOT)/bbone/lib
CONFIGUTILS_DIR :=$(SRC_ROOT)/lib/configutils

# These additional modules need to be setup in order for our tests to run
TEST_SETUP_DEPS = ${CONFIGUTILS_DIR} ${BBLIBCOMMON_DIR} ${PF9APP_DIR} ${BBMASTER_DIR} ${BBSLAVE_DIR}
TEST_VENV = ${BUILD_DIR}/test_venv
TEST_VENV_DEVELOP_CMD=${TEST_VENV}/bin/python setup.py develop

${BUILD_DIR}:
	mkdir -p $@

${TEST_VENV}: ${BUILD_DIR}
	virtualenv -p python3 ${TEST_VENV}
	${TEST_VENV}/bin/pip install setuptools==33.1.1

pre-reqs : ${TEST_VENV}
	for pkg in ${TEST_SETUP_DEPS}; do \
		cd $${pkg} && \
		${TEST_VENV_DEVELOP_CMD};\
	done

integration-test-setup: pre-reqs
	# Setup nose in addition to the pre-reqs
	source ${TEST_VENV}/bin/activate && \
	pip install nose && \
	deactivate

integration-test: integration-test-setup
	cd ${SRC_DIR} && \
	source ${TEST_VENV}/bin/activate && \
	PF9_COMMS_VERSION=1.0.0-1.2 PF9_COMMS_FILENAME=pf9-comms-1.0.0-1.2.rpm \
	PF9_VMW_MGMT_VERSION=1.0.0-1.2 PF9_VMW_MGMT_FILENAME=pf9-vmw-mgmt-1.0.0-1.2.rpm \
	PF9_MUSTER_VERSION=1.0.0-1.2 PF9_MUSTER_FILENAME=pf9-muster-1.0.0-1.2.rpm \
	${TEST_VENV}/bin/nosetests --verbosity=2 --with-xunit --xunit-file=${BUILD_DIR}/test_output.xml test/bbone_integration_test.py && \
	deactivate

clean:
	rm -rf $(BUILD_DIR)
