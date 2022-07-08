#! vim noexpandtab
# Copyright (C) 2014 Platform 9 Systems, Inc.
#

include ../../common-defs.mk

PARENT_DIR := $(abspath $(SRC_ROOT)/..)
BUILD_DIR := $(BUILD_ROOT)/janitor
JANITOR_DIR := $(SRC_ROOT)/janitor
NOTIFIER_DIR := $(SRC_ROOT)/lib/notifier
PF9_VERSION ?= 1.3.0
BUILD_NUMBER ?= 0
RPM_DIR := $(BUILD_DIR)/rpmbuild
JANITOR_SRC_STAGE = ${BUILD_DIR}/srcstage/pf9-janitor-${PF9_VERSION}
JANITOR_SRC_TARBALL = ${BUILD_DIR}/pf9-janitor-${PF9_VERSION}.tgz
PF9_OPT_DIR = ${JANITOR_SRC_STAGE}/opt/pf9
PROD_VENV = ${PF9_OPT_DIR}/janitor
# These are additional modules needed to setup for production purposes
PROD_SETUP_DEPS = ${NOTIFIER_DIR}
PROD_VENV_INSTALL_CMD=${PROD_VENV}/bin/python setup.py install
desc = "Platform9 janitor"
name = "pf9-janitor"
arch = "noarch"
GITHASH = $(shell git rev-parse --short HEAD)
package = ${RPM_DIR}/${name}-${PF9_VERSION}-${BUILD_NUMBER}.$(GITHASH).${arch}.rpm 


VENV=${PROD_VENV}
SETUP_DEPS=${PROD_SETUP_DEPS}
VENV_CMD=${PROD_VENV_INSTALL_CMD}

#TODO: Coverage zip should probably be done as part of teamcity build steps.
COVERAGE_ZIP = ${SRC_ROOT}/coverage.zip

${BUILD_DIR}:
	mkdir -p $@

${VENV}: ${BUILD_DIR}
	mkdir -p $@
	$(SRC_ROOT)/build-venv.sh ${VENV} "py3" && \
	${PROD_VENV}/bin/python ${PROD_VENV}/bin/pip install --upgrade pip setuptools && \
	${PROD_VENV}/bin/python ${PROD_VENV}/bin/pip install -r ${JANITOR_DIR}/requirements.txt \
		-c https://releases.openstack.org/constraints/upper/ussuri
	sed -i 's/buffering=0/buffering=1/g' ${PROD_VENV}/lib/python3.*/site-packages/daemon/runner.py

${JANITOR_SRC_STAGE}: pre-reqs
	mkdir -p ${JANITOR_SRC_STAGE}/var/log/pf9
	mkdir -p ${JANITOR_SRC_STAGE}/etc/pf9
	cp ${JANITOR_DIR}/etc/pf9/janitor.conf ${JANITOR_SRC_STAGE}/etc/pf9/
	mkdir -p ${BUILD_DIR}/rpmbuild
	mkdir -p ${VENV}/bin
	cp ${JANITOR_DIR}/bin/janitor-daemon.py ${VENV}/bin/
	mkdir -p ${JANITOR_SRC_STAGE}/etc/rc.d/init.d
	cp -r ${JANITOR_DIR}/etc/init.d/pf9-janitor ${JANITOR_SRC_STAGE}/etc/rc.d/init.d/


${JANITOR_SRC_TARBALL}: ${JANITOR_SRC_STAGE}
	cd ${BUILD_DIR}/srcstage && tar -czf ${JANITOR_SRC_TARBALL} *

rpm: ${JANITOR_SRC_TARBALL}
	fpm -t rpm -s dir -n ${name} \
        --description ${desc} \
        --license "Commercial" \
        --package ${package} \
        --after-install ${JANITOR_DIR}/support/after-install \
        --before-remove ${JANITOR_DIR}/support/before-remove \
        --architecture ${arch} \
        --url "http://www.platform9.com" \
        --vendor Platform9 \
        --version ${PF9_VERSION} \
        --iteration ${BUILD_NUMBER}.${GITHASH} \
        --provides ${name} \
        -C ${JANITOR_SRC_STAGE} .

	${SRC_ROOT}/sign_packages.sh ${RPM_DIR}/pf9-janitor*.rpm

pre-reqs: ${VENV}
	cd ${NOTIFIER_DIR} && ${VENV_CMD}
	cd ${JANITOR_DIR} && ${VENV_CMD}

clean:
	rm -rf $(BUILD_DIR)
	rm -rf ${COVERAGE_ZIP}
