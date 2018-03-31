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
PF9_VERSION ?= 1.5.0
BUILD_NUMBER ?= 0
GITHASH=$(shell git rev-parse --short HEAD)

HOSTAGENT_TARBALL_SRCDIR := $(BUILD_DIR)/hostagent-tarball-src
PYTHON_DIR := $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/python
VENV_DIR := $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/hostagent
HOSTAGENT_TARBALL := $(BUILD_DIR)/pf9-hostagent.tar.gz

VENV_INSTALL_CMD = $(VENV_DIR)/bin/python setup.py install
PF9APP_DIR := $(SRC_ROOT)/bbone/pf9app
BBLIBCOMMON_DIR := $(SRC_ROOT)/bbone/lib
CONFIGUTILS_DIR := $(SRC_ROOT)/lib/configutils
HOSTAGENT_DEPS = setuptools==33.1.1 \
                 $(CONFIGUTILS_DIR) \
                 $(PF9APP_DIR) \
                 $(BBLIBCOMMON_DIR) \
                 $(SRC_DIR)
SED_CMD=sed -e "s/__BUILDNUM__/$(BUILD_NUMBER)/" -e "s/__GITHASH__/$(GITHASH)/" -e "s/__VERSION__/$(PF9_VERSION)/"

PYTHON_DOWNLOAD_URL := netsvc/yum-repo-frozen/hostagent-components/python.tgz

# Include pf9-lib, which contains .so files used by all pf9 apps
SO_DOWNLOAD_URL := netsvc/yum-repo-frozen/hostagent-components/libs/pf9-lib/

$(HOSTAGENT_TARBALL_SRCDIR):
	mkdir -p $@
	mkdir -p $@/var/log/pf9
	mkdir -p $@/etc/pf9
	cp $(SRC_DIR)/etc/pf9/hostagent.conf $@/etc/pf9

$(PYTHON_DIR): $(HOSTAGENT_TARBALL_SRCDIR)
	mkdir -p $@
	wget -q -O- $(PYTHON_DOWNLOAD_URL) | tar zxf - --strip-components=3 -C $@
	mkdir -p $@/pf9-lib
	wget --no-host-directories --recursive --no-parent --accept '*.so.*' --cut-dirs=4 \
		--directory-prefix=$@/pf9-lib $(SO_DOWNLOAD_URL)

$(VENV_DIR): $(PYTHON_DIR)
	mkdir -p $@
	cd $@ && \
	virtualenv -p ../python/bin/python $@
	curl https://bootstrap.pypa.io/get-pip.py |$(VENV_DIR)/bin/python -
	$(VENV_DIR)/bin/pip install $(HOSTAGENT_DEPS)
	# Inherit global packages to use 'yum' or 'apt' which are not on PyPi
	rm -f $(VENV_DIR)/lib/python$(PYTHON_VERSION)/no-global-site-packages.txt
	cp $(SRC_DIR)/scripts/pf9-hostagent-$(TARGET_DISTRO) $(VENV_DIR)/bin/pf9-hostagent
	cp $(SRC_DIR)/bin/host-certs* $(VENV_DIR)/bin/
	cp $(SRC_DIR)/scripts/run_support_scripts.sh $(VENV_DIR)/bin
	cp $(SRC_DIR)/scripts/openport.py $(VENV_DIR)/bin
	cp $(SRC_DIR)/service_scripts/pf9-service-functions.sh $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/
	# Create a symlink so that the program names of the hostagent and the
	# init script are different. This will allow the start-stop-daemon to
	# determine if the imagelibrary is running by looking at the program names.
	cd $(VENV_DIR)/bin && ln -s pf9-hostagent pf9-hostd
	mkdir -p $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/support/allowed_commands
	cp $(SRC_DIR)/allowed_commands/* $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/support/allowed_commands
	cp $(SRC_DIR)/support_scripts/common/* $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/support
	mkdir -p $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/hostagent/extensions
	cp $(SRC_DIR)/extensions/* $(HOSTAGENT_TARBALL_SRCDIR)/opt/pf9/hostagent/extensions

