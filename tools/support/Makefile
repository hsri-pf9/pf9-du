#! vim noexpandtab
# Copyright (C) 2014 Platform 9 Systems, Inc.
#

include ../../common-defs.mk

PARENT_DIR := $(abspath $(SRC_ROOT)/..)

SRC_DIR := $(SRC_ROOT)/tools
BUILD_DIR := $(BUILD_ROOT)/du_tools

DU_TOOLS_DIR :=$(SRC_DIR)

PF9_VERSION ?= 1.3.0
BUILD_NUMBER ?= 0
RPM_DIR := $(BUILD_DIR)/rpmbuild

${BUILD_DIR}:
	mkdir -p $@

rpm: ${BUILD_DIR}
	sed -e "s/__BUILDNUM__/${BUILD_NUMBER}/" -e "s/__GITHASH__/$(shell git rev-parse --short HEAD)/" du-tools-rpm.spec > ${BUILD_DIR}/du-tools-rpm.spec
	rpmbuild -bb --define "_topdir ${RPM_DIR}" --define "_src_dir ${DU_TOOLS_DIR}" --define "_version ${PF9_VERSION}" ${BUILD_DIR}/du-tools-rpm.spec
	${SRC_ROOT}/sign_packages.sh ${RPM_DIR}/RPMS/*/pf9-du-tools*.rpm

clean:
	rm -rf $(BUILD_DIR)
