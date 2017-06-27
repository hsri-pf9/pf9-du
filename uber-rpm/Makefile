# Makefile for uber RPM for DU
NAME := pf9-du
PF9_VERSION ?= 0.0.7
GITHASH := $(shell git rev-parse --short HEAD)

SRCROOT := $(dir $(realpath $(firstword $(MAKEFILE_LIST))))
BLDROOT := $(SRCROOT)/build
STAGING := $(BLDROOT)/$(NAME)-$(PF9_VERSION)
TARBALL := $(STAGING).tar.gz
NETTOOL := $(STAGING)/opt/pf9/du-customize/customize-pf9-installer/nettool

GLIDE_VERSION := 0.12.3
GLIDE_ARCH := linux-amd64
GLIDE_TARBALL := glide-v$(GLIDE_VERSION)-$(GLIDE_ARCH).tar.gz
GLIDE_URL := https://github.com/Masterminds/glide/releases/download/v$(GLIDE_VERSION)/$(GLIDE_TARBALL)
GLIDE := $(BLDROOT)/$(GLIDE_ARCH)/glide

RPM := $(BLDROOT)/RPMS/$(NAME)-$(PF9_VERSION)-0.22c871a.x86_64.rpm
MOCK := /usr/bin/mock -r epel-7-x86_64
BUILD_NUMBER ?= 0

build: $(RPM)

$(RPM): $(TARBALL)
	$(MOCK) --buildsrpm --spec $(BLDROOT)/$(NAME).spec --sources $(BLDROOT) --resultdir $(BLDROOT)/SRPMS
	$(MOCK) --rebuild $(BLDROOT)/SRPMS/*.src.rpm --resultdir $(BLDROOT)/RPMS
	$(SRCROOT)/../sign_packages.sh $(BLDROOT)/RPMS/pf9-du*.rpm


$(TARBALL): $(STAGING) $(NETTOOL)
	cd $(BLDROOT) && tar -zcf $(TARBALL) $(NAME)-$(PF9_VERSION)

nettool: $(NETTOOL)
$(NETTOOL): $(STAGING) $(GLIDE)
	export GOPATH="$(SRCROOT)/nettool" && \
	export CGO_ENABLED=0 && \
	cd $(SRCROOT)/nettool/src/nettool && \
	$(GLIDE) install && \
	go vet nettool nettool/cmd && \
	go build -o $@ nettool

$(GLIDE):
	cd $(BLDROOT) && \
	wget $(GLIDE_URL) && \
	tar xf $(GLIDE_TARBALL)

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

clean:
	rm -rf "$(BLDROOT)"

.PHONY: build clean nettool
