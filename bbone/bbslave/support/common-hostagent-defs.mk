# Host agent definitions common to all distros
#
# Input: the following variables are expected:
# SRC_ROOT
# BUILD_DIR
# PYTHON_VERSION
#
# Output: the following variables are defined:
# SRC_DIR
# VENV_DIR
# HOSTAGENT_TARBALL
# HOSTAGENT_TARBALL_SRCDIR
# SED_CMD

SRC_DIR := $(SRC_ROOT)/bbone/bbslave
VERSION ?= 1.0.0
BUILD_NUMBER ?= 0
GITHASH=$(shell git rev-parse --short HEAD)

HOSTAGENT_TARBALL_SRCDIR := $(BUILD_DIR)/hostagent-tarball-src
VENV_DIR := $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/hostagent
HOSTAGENT_TARBALL := $(BUILD_DIR)/pf9-hostagent.tar.gz

VENV_INSTALL_CMD=$(VENV_DIR)/bin/python setup.py install
PF9APP_DIR :=$(SRC_ROOT)/bbone/pf9app
BBLIBCOMMON_DIR :=$(SRC_ROOT)/bbone/lib
CONFIGUTILS_DIR :=$(SRC_ROOT)/lib/configutils
SED_CMD=sed -e "s/__BUILDNUM__/$(BUILD_NUMBER)/" -e "s/__GITHASH__/$(GITHASH)/" -e "s/__VERSION__/$(VERSION)/"

$(HOSTAGENT_TARBALL_SRCDIR):
	mkdir -p $@
	mkdir -p $@/etc/pf9
	cp $(SRC_DIR)/etc/pf9/hostagent.conf $@/etc/pf9

$(VENV_DIR): | $(HOSTAGENT_TARBALL_SRCDIR)
	virtualenv $@
	cd $(CONFIGUTILS_DIR) && $(VENV_INSTALL_CMD)
	cd $(PF9APP_DIR) && $(VENV_INSTALL_CMD)
	cd $(BBLIBCOMMON_DIR) && $(VENV_INSTALL_CMD)
	cd $(SRC_DIR) && $(VENV_INSTALL_CMD)
	# Inherit global packages to use 'yum' or 'apt' which are not on PyPi
	rm -f $(VENV_DIR)/lib/$(PYTHON_VERSION)/no-global-site-packages.txt
	cp $(SRC_DIR)/scripts/pf9-hostagent $(VENV_DIR)/bin

