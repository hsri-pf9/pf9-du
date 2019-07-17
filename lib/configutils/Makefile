#! vim noexpandtab
# Copyright (C) 2013 Platform 9 Systems, Inc.
#

include ../../common-defs.mk

PARENT_DIR := $(abspath $(SRC_ROOT)/..)

SRC_DIR := $(SRC_ROOT)/lib/configutils
BUILD_DIR := $(BUILD_ROOT)/configutils

$(BUILD_DIR):
	mkdir -p $@

TEST_VENV = ${BUILD_DIR}/test_venv
TEST_VENV_DEVELOP_CMD=${TEST_VENV}/bin/python setup.py develop
COVERAGE_ZIP = ${BUILD_DIR}/coverage.zip
DISTUTILS_DEBUG = 1

${TEST_VENV}: ${BUILD_DIR}
	virtualenv ${TEST_VENV}
	${TEST_VENV}/bin/pip install six==1.12.0

pre-reqs : ${TEST_VENV}
	cd ${SRC_DIR} && \
	${TEST_VENV_DEVELOP_CMD}

unit-test-setup: pre-reqs
	# Setup up nose and coverage in addition to pre-reqs
	source ${TEST_VENV}/bin/activate && \
	pip install nose && \
	pip install coverage && \
	deactivate

unit-test: unit-test-setup
	cd ${SRC_DIR} && \
	${TEST_VENV}/bin/nosetests --with-coverage --cover-html --cover-html-dir=${BUILD_DIR}/coverage \
			--cover-package=configutils --verbosity=2 --with-xunit --xunit-file=${BUILD_DIR}/test_output.xml && \
	cd ${BUILD_DIR}/coverage && \
	zip -q ${COVERAGE_ZIP} *


clean:
	rm -rf $(BUILD_DIR)
