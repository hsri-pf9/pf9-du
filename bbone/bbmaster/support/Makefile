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

# These additional modules need to be setup in order for our tests to run
TEST_SETUP_DEPS = ${BBLIBCOMMON_DIR} ${SRC_ROOT}/bbone/bbslave ${PF9APP_DIR} ${CONFIGUTILS_DIR}
TEST_VENV = ${BUILD_DIR}/bbmaster_venv
TEST_VENV_DEVELOP_CMD=${TEST_VENV}/bin/python setup.py develop

#TODO: Coverage zip should probably be done as part of teamcity build steps.
COVERAGE_ZIP = ${SRC_ROOT}/coverage.zip

${BUILD_DIR}:
	mkdir -p $@

${TEST_VENV}: ${BUILD_DIR}
	virtualenv ${TEST_VENV}

pre-reqs : ${TEST_VENV}
	for pkg in ${TEST_SETUP_DEPS}; do \
		cd $${pkg};\
		${TEST_VENV_DEVELOP_CMD};\
	done;\
	cd ${BBMASTER_DIR};\
	${TEST_VENV_DEVELOP_CMD};

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


clean:
	rm -rf $(BUILD_DIR)
	if [ -f ${COVERAGE_ZIP} ]; \
	then \
		rm ${COVERAGE_ZIP}; \
	fi;
