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
BUILD_IMAGE :=artifactory.platform9.horse/docker-local/py39-build-image:latest

# These additional modules need to be setup in order for our tests to run
TEST_SETUP_DEPS = ${CONFIGUTILS_DIR} ${BBLIBCOMMON_DIR} ${PF9APP_DIR} ${BBMASTER_DIR} ${BBSLAVE_DIR}
TEST_VENV = ${BUILD_DIR}/test_venv
TEST_VENV_DEVELOP_CMD=${TEST_VENV}/bin/python setup.py develop

${BUILD_DIR}:
	mkdir -p $@

${TEST_VENV}: ${BUILD_DIR}
	python3.9 -m venv ${TEST_VENV}
	${TEST_VENV}/bin/pip install --upgrade pip setuptools
	${TEST_VENV}/bin/pip install cryptography==2.8

pre-reqs : ${TEST_VENV}
	for pkg in ${TEST_SETUP_DEPS}; do \
		cd $${pkg} && \
		${TEST_VENV_DEVELOP_CMD};\
	done

integration-test-setup: pre-reqs
	# Setup nose in addition to the pre-reqs
	${TEST_VENV}/bin/pip install nose

integration-test-in-docker: integration-test-setup
	cd ${SRC_DIR} && \
	PF9_COMMS_VERSION=1.0.0-1.2 PF9_COMMS_FILENAME=pf9-comms-1.0.0-1.2.rpm \
	PF9_MUSTER_VERSION=1.0.0-1.2 PF9_MUSTER_FILENAME=pf9-muster-1.0.0-1.2.rpm \
	${TEST_VENV}/bin/nosetests --verbosity=2 --with-xunit --xunit-file=${BUILD_DIR}/test_output.xml test/bbone_integration_test.py

integration-test:
	docker run  --rm -i \
	    -u $(shell id -u):$(shell id -g) \
	    -v ${SRC_ROOT}:/src/pf9-du \
	    -v /etc/passwd:/etc/passwd \
	    -w /src/pf9-du/bbone/support \
	    ${BUILD_IMAGE} /bin/bash -c "make integration-test-in-docker"	

clean:
	rm -rf $(BUILD_DIR)
