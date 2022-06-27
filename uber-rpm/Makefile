# Makefile for uber RPM for DU
NAME := pf9-du
PF9_VERSION ?= 0.0.7
GITHASH := $(shell git rev-parse --short HEAD)

SRCROOT := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
BLDROOT := $(SRCROOT)/build
STAGING := $(BLDROOT)/$(NAME)-$(PF9_VERSION)
TARBALL := $(STAGING).tar.gz
NETTOOL := $(STAGING)/opt/pf9/du-customize/customize-pf9-installer/nettool

# Do some extra handling for gimme installs because the docker container
# builds don't have user home dir set as expected.
IN_CONTAINER := $(shell grep -q docker /proc/1/cgroup; echo $$?)
ifeq ($(IN_CONTAINER), 1)
	GIMME_HOME := ~
else
	GIMME_HOME := $(BLDROOT)/../../build/.home
endif

RPM := $(BLDROOT)/RPMS/$(NAME)-$(PF9_VERSION)-0.22c871a.x86_64.rpm
MOCK := /usr/bin/mock -r epel-7-x86_64
BUILD_NUMBER ?= 0

NOCERT_STAGE_REDHAT = $(BLDROOT)/installer-stage/redhat
NOCERT_STAGE_DEBIAN = $(BLDROOT)/installer-stage/debian
NOCERT_REDHAT = $(BLDROOT)/platform9-install-redhat.sh
NOCERT_DEBIAN = $(BLDROOT)/platform9-install-debian.sh
INSTALLER_SCRIPTS = $(SRCROOT)/du-customize/customize-pf9-installer

build: $(RPM)

$(RPM): $(TARBALL)
	$(MOCK) --buildsrpm --spec $(BLDROOT)/$(NAME).spec --sources $(BLDROOT) --resultdir $(BLDROOT)/SRPMS
	$(MOCK) --rebuild $(BLDROOT)/SRPMS/*.src.rpm --resultdir $(BLDROOT)/RPMS
	$(SRCROOT)/../sign_packages.sh $(BLDROOT)/RPMS/pf9-du*.rpm


$(TARBALL): $(STAGING) $(NETTOOL)
	cd $(BLDROOT) && tar -zcf $(TARBALL) $(NAME)-$(PF9_VERSION)

nettool: $(NETTOOL)
$(NETTOOL): $(STAGING)
	curl -L -o $(BLDROOT)/gimme https://raw.githubusercontent.com/travis-ci/gimme/master/gimme && \
	chmod a+x $(BLDROOT)/gimme && \
	mkdir -p $(BLDROOT)/gimme-1.18 && \
	$(BLDROOT)/gimme 1.18 && \
	source $(GIMME_HOME)/.gimme/envs/go1.18.linux.amd64.env && \
	cd $(SRCROOT)/nettool && \
	go build -o $@ nettool


$(STAGING):
	mkdir -p $(STAGING)/opt/pf9/du-customize
	mkdir -p $(STAGING)/etc/pf9
	cp -a $(SRCROOT)/du-customize $(STAGING)/opt/pf9/
	cp -a $(SRCROOT)/controller/etc/global.conf $(STAGING)/etc/pf9
	sed -e "s/__BUILDNUM__/$(BUILD_NUMBER)/" \
	    -e "s/__GITHASH__/$(GITHASH)/" \
	    -e "s/__VERSION__/$(PF9_VERSION)/" \
	    $(SRCROOT)/$(NAME).spec > $(BLDROOT)/$(NAME).spec

unit-test: $(NETTOOL)
	(cd "./du-customize/customize-pf9-installer/tests/" && bash ./test_check_os_version.sh)
	(cd "./du-customize/customize-pf9-installer/tests/" && bash ./test_nettool.sh $<)

redhat-installer-nocert: $(NOCERT_REDHAT)

debian-installer-nocert: $(NOCERT_DEBIAN)

$(NOCERT_REDHAT): nettool
	rm -rf $(NOCERT_STAGE_REDHAT) && \
	mkdir -p $(NOCERT_STAGE_REDHAT) && \
	cp $(NETTOOL) $(NOCERT_STAGE_REDHAT)/ && \
	cp -r $(INSTALLER_SCRIPTS)/* $(NOCERT_STAGE_REDHAT)/ && \
	cd $(NOCERT_STAGE_REDHAT) && \
	DISTROS=redhat HOSTAGENT_SKIP_CERTS=1 INSTALLER_LOCATION=$@ ./build-installer.sh dummy

$(NOCERT_DEBIAN): nettool
	rm -rf $(NOCERT_STAGE_DEBIAN) && \
	mkdir -p $(NOCERT_STAGE_DEBIAN) && \
	cp $(NETTOOL) $(NOCERT_STAGE_DEBIAN)/ && \
	cp -r $(INSTALLER_SCRIPTS)/* $(NOCERT_STAGE_DEBIAN)/ && \
	cd $(NOCERT_STAGE_DEBIAN) && \
	DISTROS=debian HOSTAGENT_SKIP_CERTS=1 INSTALLER_LOCATION=$@ ./build-installer.sh dummy

clean:
	rm -rf "$(BLDROOT)"

.PHONY: build clean nettool
