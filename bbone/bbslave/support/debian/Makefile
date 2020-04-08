#! vim noexpandtab
# Copyright (C) 2014 Platform 9 Systems, Inc.
#
# Usage: make hostagent-tarball-debian
#

include ../../../../common-defs.mk

BUILD_DIR := $(BUILD_ROOT)/hostagent/debian
PYTHON_VERSION = 2.7

# This defines SRC_DIR, VENV_DIR, HOSTAGENT_TARBALL,
# HOSTAGENT_TARBALL_SRCDIR and SED_CMD
include ../common-hostagent-defs.mk

$(HOSTAGENT_TARBALL): | $(VENV_DIR)
	mkdir -p $(HOSTAGENT_TARBALL_SRCDIR)/etc/sudoers.d
	mkdir -p $(HOSTAGENT_TARBALL_SRCDIR)/var/opt/pf9
	mkdir -p $(HOSTAGENT_TARBALL_SRCDIR)/var/cache/pf9apps
	cp $(SRC_DIR)/support_scripts/debian/* $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/support/
	cp $(SRC_DIR)/service_scripts/pf9-hostagent-deb-init $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/hostagent/
	cp $(SRC_DIR)/service_scripts/pf9-hostagent-systemd $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/hostagent/
	cp $(SRC_DIR)/service_scripts/pf9-hostagent-systemd $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/hostagent/
	cp $(SRC_DIR)/service_scripts/pf9-hostagent.env $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/hostagent/
	cp $(SRC_DIR)/service_scripts/pf9-hostagent-prestart.sh $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/hostagent/
	cp $(SRC_DIR)/etc/sudoers.d/pf9-hostagent-debian $(HOSTAGENT_TARBALL_SRCDIR)/etc/sudoers.d/pf9-hostagent
	cp $(SRC_DIR)/support/debian/hostagent-deb-build.sh $(HOSTAGENT_TARBALL_SRCDIR)
	cp $(SRC_DIR)/support/debian/before-install.sh $(HOSTAGENT_TARBALL_SRCDIR)
	cp $(SRC_DIR)/support/debian/after-install.sh $(HOSTAGENT_TARBALL_SRCDIR)
	cp $(SRC_DIR)/support/debian/before-remove.sh $(HOSTAGENT_TARBALL_SRCDIR)
	cp $(SRC_DIR)/support/debian/after-remove.sh $(HOSTAGENT_TARBALL_SRCDIR)
	cp $(SRC_DIR)/support/debian/hostagent-deb-build.sh $(HOSTAGENT_TARBALL_SRCDIR)
	cp $(SRC_DIR)/scripts/pf9-apt $(VENV_DIR)/bin
	cd $(HOSTAGENT_TARBALL_SRCDIR) && \
	tar -czf $(HOSTAGENT_TARBALL) *

hostagent-tarball-rpm-debian: $(HOSTAGENT_TARBALL)
	$(SED_CMD) ${SRC_DIR}/support/debian/46-customize-hostagent-deb > ${BUILD_DIR}/46-customize-hostagent-deb
	chmod +x ${BUILD_DIR}/46-customize-hostagent-deb
	$(SED_CMD)  hostagent-tarball-rpm.spec > ${BUILD_DIR}/hostagent-tarball-rpm.spec
	mkdir ${BUILD_DIR}/../SOURCES
	cp -r ${BUILD_DIR}/* ${BUILD_DIR}/../SOURCES
	mv ${BUILD_DIR}/../SOURCES ${BUILD_DIR}
	rpmbuild -bb $(BUILD_DIR)/hostagent-tarball-rpm.spec --define "_topdir $(BUILD_DIR)"
	$(SRC_ROOT)/sign_packages.sh $(BUILD_DIR)/RPMS/*/pf9-hostagent-tarball-debian*.rpm

hostagent-tarball-rpm-debian hostagent-deb-nocert: TARGET_DISTRO = debian

# build a hostagent rpm with no certs, no DU_FQDN and no amqp credentials
hostagent-deb-nocert: $(HOSTAGENT_TARBALL)
	$(SED_CMD) ${SRC_DIR}/support/debian/46-customize-hostagent-deb > ${BUILD_DIR}/46-customize-hostagent-deb && \
	chmod +x ${BUILD_DIR}/46-customize-hostagent-deb && \
	HOSTAGENT_SKIP_CERTS=1 DU_FQDN='' ${BUILD_DIR}/46-customize-hostagent-deb '' ''

clean:
	rm -rf $(BUILD_DIR)
