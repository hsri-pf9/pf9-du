#! vim noexpandtab
# Copyright (C) 2013 Platform 9 Systems, Inc.
#
# Usage: make hostagent-tarball
#
# CentOS 6.4 build environment requirements:
#
# RPMs: make gcc git
# The user running make must have sudo (with no password required) privilege.

include ../../../common-defs.mk

PARENT_DIR := $(abspath $(SRC_ROOT)/..)

MYSELF := $(shell whoami)
SRC_DIR := $(SRC_ROOT)/bbone/bbslave
BUILD_DIR := $(BUILD_ROOT)/hostagent
RPMBUILD_DIR := $(BUILD_DIR)/rpmbuild

VERSION ?= 1.0.0
HOST_IP ?= 10.1.10.254

HOSTAGENT_RPM := $(BUILD_DIR)/pf9-hostagent.rpm
HOSTAGENT_TARBALL_SRCDIR := $(BUILD_DIR)/hostagent-tarball-src

OPT_PF9_DIR := $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9
VENV_DIR := $(OPT_PF9_DIR)/hostagent

HOSTAGENT_TARBALL_EXPANDEDDIR := $(BUILD_DIR)/hostagent-tarball-expanded
HOSTAGENT_TARBALL := $(BUILD_DIR)/pf9-hostagent.tar.gz

HOSTAGENT_ROOT := $(RPM_TAR_ROOT)/rpmsrc

VENV_INSTALL_CMD=$(VENV_DIR)/bin/python setup.py install

BBSLAVE_DIR :=$(SRC_DIR)
PF9APP_DIR :=$(SRC_ROOT)/bbone/pf9app
BBLIBCOMMON_DIR :=$(SRC_ROOT)/bbone/lib
CONFIGUTILS_DIR :=$(SRC_ROOT)/lib/configutils

$(BUILD_DIR): | $(VENV_DIR)
	mkdir -p $@

$(OPT_PF9_DIR):
	sudo mkdir -p $@
	sudo chown $(MYSELF) $@

# Site packages required: bbslave needs 'yum' which is not available on PyPi
$(VENV_DIR): | $(OPT_PF9_DIR)
	virtualenv --system-site-packages $@

$(HOSTAGENT_TARBALL_EXPANDEDDIR):
	rm -fr $@
	mkdir -p $@

$(HOSTAGENT_TARBALL_SRCDIR):
	rm -fr $@
	mkdir -p $@
	cp -r $(BBSLAVE_DIR)/etc $@/

install-bbslave: | $(BUILD_DIR)
	cd $(CONFIGUTILS_DIR);\
	$(VENV_INSTALL_CMD)
	cd $(PF9APP_DIR);\
	$(VENV_INSTALL_CMD)
	cd $(BBLIBCOMMON_DIR);\
	$(VENV_INSTALL_CMD)
	cd $(BBSLAVE_DIR);\
	$(VENV_INSTALL_CMD)

$(HOSTAGENT_TARBALL): | $(HOSTAGENT_TARBALL_SRCDIR) install-bbslave
	cp $(SRC_DIR)/support/hostagent.spec $(HOSTAGENT_TARBALL_SRCDIR)
	cp $(SRC_DIR)/support/hostagent-rpmbuild.sh $(HOSTAGENT_TARBALL_SRCDIR)
	cp $(SRC_DIR)/scripts/pf9-hostagent $(VENV_DIR)/bin
	cd $(HOSTAGENT_TARBALL_SRCDIR);\
	tar -czf $(HOSTAGENT_TARBALL) *

hostagent-expand-tarball: | $(HOSTAGENT_TARBALL_EXPANDEDDIR) $(HOSTAGENT_TARBALL)
	tar -xzf $(HOSTAGENT_TARBALL) -C $(HOSTAGENT_TARBALL_EXPANDEDDIR)

# The creation of RPM will be at a time when we won't have access to
# the make system, so the hostagent-rpmbuild should be self contained
# and needs only the expanded tar file to exist and optionally pass in as a parameter
# - Expanded directory of tarball
# - (Optional) Version for the rpm
# - (Optional) Ip/DNS name of the service
$(HOSTAGENT_RPM): hostagent-expand-tarball
	$(HOSTAGENT_TARBALL_EXPANDEDDIR)/hostagent-rpmbuild.sh $(RPMBUILD_DIR) $(HOSTAGENT_TARBALL_EXPANDEDDIR) $(VERSION) $(HOST_IP)

hostagent-rpm: $(HOSTAGENT_RPM)

hostagent-tarball: $(HOSTAGENT_TARBALL)

clean:
	sudo rm -rf $(BUILD_DIR)
