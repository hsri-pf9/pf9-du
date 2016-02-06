#! vim noexpandtab
# Copyright (C) 2014 Platform 9 Systems, Inc.
#

include ../../common-defs.mk

PARENT_DIR := $(abspath $(SRC_ROOT)/..)

SRC_DIR := $(SRC_ROOT)/janitor
BUILD_DIR := $(BUILD_ROOT)/janitor

JANITOR_DIR :=$(SRC_DIR)
NOTIFIER_DIR :=$(SRC_ROOT)/lib/notifier

PF9_VERSION ?= 1.3.0
BUILD_NUMBER ?= 0
RPM_DIR := $(BUILD_DIR)/rpmbuild
MOCK = /usr/bin/mock -r epel-6-x86_64

JANITOR_SRC_STAGE = ${BUILD_DIR}/srcstage/pf9-janitor-${PF9_VERSION}
JANITOR_SRC_TARBALL = ${BUILD_DIR}/pf9-janitor-${PF9_VERSION}.tgz
PF9_OPT_DIR = ${JANITOR_SRC_STAGE}/opt/pf9
PROD_VENV = ${PF9_OPT_DIR}/janitor
# These are additional modules needed to setup for production purposes
PROD_SETUP_DEPS = ${NOTIFIER_DIR}
PROD_VENV_INSTALL_CMD=${PROD_VENV}/bin/python setup.py install


VENV=${PROD_VENV}
SETUP_DEPS=${PROD_SETUP_DEPS}
VENV_CMD=${PROD_VENV_INSTALL_CMD}

#TODO: Coverage zip should probably be done as part of teamcity build steps.
COVERAGE_ZIP = ${SRC_ROOT}/coverage.zip

${BUILD_DIR}:
	mkdir -p $@

${VENV}: ${BUILD_DIR}
	mkdir -p $@
	virtualenv ${VENV}

${JANITOR_SRC_STAGE}: pre-reqs
	mkdir -p ${JANITOR_SRC_STAGE}/var/log/pf9
	mkdir -p ${JANITOR_SRC_STAGE}/etc/pf9
	cp ${JANITOR_DIR}/etc/pf9/janitor.conf ${JANITOR_SRC_STAGE}/etc/pf9/

	mkdir -p ${VENV}/bin
	cp ${JANITOR_DIR}/bin/janitor-daemon.py ${VENV}/bin/

	mkdir -p ${JANITOR_SRC_STAGE}/etc/rc.d/init.d
	cp -r ${JANITOR_DIR}/etc/init.d/pf9-janitor ${JANITOR_SRC_STAGE}/etc/rc.d/init.d/


${JANITOR_SRC_TARBALL}: ${JANITOR_SRC_STAGE}
	cd ${BUILD_DIR}/srcstage && tar -czf ${JANITOR_SRC_TARBALL} *

rpm: ${JANITOR_SRC_TARBALL}
	sed -e "s/__BUILDNUM__/${BUILD_NUMBER}/" -e "s/__VERSION__/${PF9_VERSION}/" \
	    -e "s/__GITHASH__/$(shell git rev-parse --short HEAD)/" janitor-rpm.spec \
	    > ${BUILD_DIR}/janitor-rpm.spec
	${MOCK} --buildsrpm --sources ${BUILD_DIR} --spec ${BUILD_DIR}/janitor-rpm.spec --resultdir ${RPM_DIR}
	mv ${RPM_DIR}/*.src.rpm ${BUILD_DIR}
	${MOCK} --rebuild --resultdir ${RPM_DIR} ${BUILD_DIR}/*.src.rpm
	rm -f ${BUILD_DIR}/*.src.rpm
	${SRC_ROOT}/sign_packages.sh ${RPM_DIR}/pf9-janitor*.rpm

pre-reqs: ${VENV}
	cd ${NOTIFIER_DIR} && ${VENV_CMD}
	cd ${JANITOR_DIR} && ${VENV_CMD}


clean:
	rm -rf $(BUILD_DIR)
	rm -rf ${COVERAGE_ZIP}
