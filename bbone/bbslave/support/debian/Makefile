#! vim noexpandtab
# Copyright (C) 2014 Platform 9 Systems, Inc.
#
# Usage: make hostagent-tarball-debian
#

include ../../../../common-defs.mk

BUILD_DIR := $(BUILD_ROOT)/hostagent/debian
PYTHON_VERSION = 2.7

# This defines SRC_DIR, HOSTAGENT_TARBALL and SED_CMD
include ../common-hostagent-defs.mk

hostagent-tarball-rpm-debian: $(HOSTAGENT_TARBALL)
	$(SED_CMD) ${SRC_DIR}/support/debian/46-customize-hostagent-deb > ${BUILD_DIR}/46-customize-hostagent-deb
	chmod +x ${BUILD_DIR}/46-customize-hostagent-deb
	$(SED_CMD)  hostagent-tarball-rpm.spec > ${BUILD_DIR}/hostagent-tarball-rpm.spec
	mkdir ${BUILD_DIR}/../SOURCES
	cp -r ${BUILD_DIR}/* ${BUILD_DIR}/../SOURCES
	mv ${BUILD_DIR}/../SOURCES ${BUILD_DIR}
	rpmbuild -bb $(BUILD_DIR)/hostagent-tarball-rpm.spec --define "_topdir $(BUILD_DIR)"

clean:
	rm -rf $(BUILD_DIR)
