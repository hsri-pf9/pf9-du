# Copyright (c) 2017, Platform9 Systems. All rights reserved.

.SUFFIXES:
.PHONY: clean push image stage dist

PF9_VERSION ?= 3.0.0
BUILD_NUMBER ?= 0
GITHASH=$(shell git rev-parse --short HEAD)

SRCROOT = $(abspath $(dir $(lastword $(MAKEFILE_LIST)))/../..)
BLDROOT = $(SRCROOT)/build
STAGE = $(BLDROOT)/resmgr/container
$(shell mkdir -p $(STAGE))
ARTIFACTS=$(BLDROOT)/artifacts

RESMGR_DIST = $(STAGE)/resmgr-sdist.tgz
$(RESMGR_DIST): SETUP_ROOT = $(SRCROOT)/resmgr

BBLIB_DIST = $(STAGE)/bblib-sdist.tgz
$(BBLIB_DIST): SETUP_ROOT = $(SRCROOT)/bbone/lib

BBMASTER_DIST = $(STAGE)/bbmaster-sdist.tgz
$(BBMASTER_DIST): SETUP_ROOT = $(SRCROOT)/bbone/bbmaster

CONFIGUTILS_DIST = $(STAGE)/configutils-sdist.tgz
$(CONFIGUTILS_DIST): SETUP_ROOT = $(SRCROOT)/lib/configutils

NOTIFIER_DIST = $(STAGE)/notifier-sdist.tgz
$(NOTIFIER_DIST): SETUP_ROOT = $(SRCROOT)/lib/notifier

RABBIT_DIST = $(STAGE)/rabbitmgmt-sdist.tgz
$(RABBIT_DIST): SETUP_ROOT = $(SRCROOT)/lib/rabbit

FIRKINIZE_DIST = $(STAGE)/firkinize-sdist.tgz
$(FIRKINIZE_DIST): SETUP_ROOT = $(abspath $(SRCROOT)/../firkinize)

DISTS = $(RESMGR_DIST) $(BBLIB_DIST) $(BBMASTER_DIST) $(CONFIGUTILS_DIST) \
        $(NOTIFIER_DIST) $(RABBIT_DIST) $(FIRKINIZE_DIST)

dist: $(DISTS)

Y2J = $(SRCROOT)/resmgr/container/y2j.py
APP_METADATA_YAML = $(SRCROOT)/resmgr/container/app_metadata.yaml
APP_METADATA_JSON = $(STAGE)/app_metadata.json

# FIXME - Do NOT copy paste the logic below if we add deb support. Come up with
# a way to parameterize it!

HOSTAGENT_RPM = $(BLDROOT)/hostagent/redhat-nocert/rpm-build/RPMS/x86_64/pf9-hostagent-$(PF9_VERSION)-$(BUILD_NUMBER).$(GITHASH).x86_64.rpm
HOSTAGENT_DEB = $(BLDROOT)/hostagent/debian-nocert/deb-build/DEBS/x86_64/pf9-hostagent-$(PF9_VERSION)-$(BUILD_NUMBER).$(GITHASH).x86_64.deb
REDHAT_INSTALLER_SCRIPT = $(SRCROOT)/uber-rpm/build/platform9-install-redhat.sh
DEBIAN_INSTALLER_SCRIPT = $(SRCROOT)/uber-rpm/build/platform9-install-debian.sh

# make sure firmware and role artifacts are available. FIXME: This stuff also
# appears in the nginx container, from which the files are actually served
# through the privateweb_privatefiles sni proxy to port 9080 on nginx. They
# need to be here so that bbmaster knows about them, and so resmgr can load
# the json config (for 'roles').
COMMS_RPM ?= $(shell find $(ARTIFACTS) -name pf9-comms*.rpm)
ifeq ($(wildcard $(COMMS_RPM)),)
    $(error There must be a pf9-comms rpm in $(ARTIFACTS))
endif

COMMS_DEB ?= $(shell find $(ARTIFACTS) -name pf9-comms*.deb)
ifeq ($(wildcard $(COMMS_DEB)),)
    $(error There must be a pf9-comms deb in $(ARTIFACTS))
endif

VMW_MGMT_RPM ?= $(shell find $(ARTIFACTS) -name pf9-vmw-mgmt*.rpm)
ifeq ($(wildcard $(VMW_MGMT_RPM)),)
    $(error There must be a pf9-vmw-mgmt rpm in $(ARTIFACTS))
endif

MUSTER_WRAPPER ?= $(shell find $(ARTIFACTS) -name pf9-muster-wrapper*.rpm)
ifeq ($(wildcard $(MUSTER_WRAPPER)),)
    $(error There must be a pf9-muster-wrapper rpm in $(ARTIFACTS))
endif

KUBE_WRAPPER ?= $(shell find $(ARTIFACTS) -name pf9-kube-wrapper*.rpm)
ifeq ($(wildcard $(KUBE_WRAPPER)),)
    $(error There must be a pf9-kubewrapper rpm in $(ARTIFACTS))
endif

PACKAGELIST_RPM = $(STAGE)/opt/pf9/www/private/nocert-packagelist.rpm
PACKAGELIST_DEB = $(STAGE)/opt/pf9/www/private/nocert-packagelist.deb
PACKAGELIST_LINES_COMMON = etc/pf9/certs/hostagent/cert.pem \
                           etc/pf9/certs/hostagent/key.pem \
                           etc/pf9/certs/ca/cert.pem \
                           etc/pf9/hostagent.conf
PACKAGELIST_LINES_RPM = $(notdir $(HOSTAGENT_RPM)) \
                        $(notdir $(COMMS_RPM)) \
			$(notdir $(VMW_MGMT_RPM))

PACKAGELIST_LINES_DEB = $(notdir $(HOSTAGENT_DEB)) \
                        $(notdir $(COMMS_DEB))

BUILD_ID := $(BUILD_NUMBER)
CONTAINER_IMG ?= 514845858982.dkr.ecr.us-west-1.amazonaws.com/pf9-resmgr
IMAGE_TAG ?= $(or $(PF9_VERSION), $(PF9_VERSION), "latest")-$(BUILD_ID)
BRANCH_NAME ?= $(or $(TEAMCITY_BUILD_BRANCH), $(TEAMCITY_BUILD_BRANCH), $(shell git symbolic-ref --short HEAD))

$(DISTS):
	cd $(SETUP_ROOT) && \
	rm -f dist/* && \
	python setup.py sdist && \
	cp -vf dist/* $@

$(HOSTAGENT_RPM):
	make -C $(SRCROOT)/bbone/bbslave/support/redhat hostagent-rpm-nocert

$(HOSTAGENT_DEB):
	make -C $(SRCROOT)/bbone/bbslave/support/debian hostagent-deb-nocert

$(REDHAT_INSTALLER_SCRIPT):
	make -C $(SRCROOT)/uber-rpm redhat-installer-nocert

$(DEBIAN_INSTALLER_SCRIPT):
	make -C $(SRCROOT)/uber-rpm debian-installer-nocert

# the installer script doesn't really need to be included in the container
# here, but it does need to be built and provided as an artifact to the
# nginx container build so it can be served publically from there. Having it
# here allows us to test hostagent installation without nginx.

stage: dist $(HOSTAGENT_RPM) $(REDHAT_INSTALLER_SCRIPT) $(HOSTAGENT_DEB) $(DEBIAN_INSTALLER_SCRIPT)
	cp -rv $(SRCROOT)/resmgr/container/* $(STAGE)/
	python $(Y2J) $(APP_METADATA_YAML) > $(APP_METADATA_JSON)
	cp -v $(SRCROOT)/resmgr/upper-constraints.txt $(STAGE)/
	cp -v $(MUSTER_WRAPPER) $(KUBE_WRAPPER) $(STAGE)/
	private=$(STAGE)/opt/pf9/www/private && \
	mkdir -p $${private} && \
	cp -v $(HOSTAGENT_RPM) $(REDHAT_INSTALLER_SCRIPT) $(HOSTAGENT_DEB) $(DEBIAN_INSTALLER_SCRIPT) $(COMMS_RPM) $(COMMS_DEB) $(VMW_MGMT_RPM) \
		  $${private} && \
	rm -fv $(PACKAGELIST_RPM) && \
	for line in $(PACKAGELIST_LINES_COMMON); do \
		echo $${line} >> $(PACKAGELIST_RPM); \
		echo $${line} >> $(PACKAGELIST_DEB); \
	done && \
	for line in $(PACKAGELIST_LINES_RPM); do \
		echo $${line} >> $(PACKAGELIST_RPM); \
	done && \
	for line in $(PACKAGELIST_LINES_DEB); do \
		echo $${line} >> $(PACKAGELIST_DEB); \
	done && \
	echo "$(PACKAGELIST_RPM):" && \
	cat $(PACKAGELIST_RPM) &&\
	echo "$(PACKAGELIST_DEB):" && \
	cat $(PACKAGELIST_DEB)

$(BLDROOT):
	mkdir -p $@

$(BLDROOT)/container-tag: $(BLDROOT)
	echo -ne "$(IMAGE_TAG)" >$@

image: stage
	docker build --rm -t $(CONTAINER_IMG):$(IMAGE_TAG) \
		--build-arg BUILD_ID=$(BUILD_ID) \
		--build-arg VERSION=$(PF9_VERSION) \
		--build-arg BRANCH=$(BRANCH_NAME) \
		--build-arg APP_METADATA=`cat $(APP_METADATA_JSON)` \
		$(STAGE)

# This assumes that credentials for the aws tool are configured, either in
# ~/.aws/config or in AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
push: image $(BLDROOT)/container-tag
	docker push $(CONTAINER_IMG):$(IMAGE_TAG) || \
	(aws ecr get-login --region=us-west-1 |sh && \
	docker push $(CONTAINER_IMG):$(IMAGE_TAG))

clean:
	rm -rf $(STAGE)
	images=$$(docker images -q -f dangling=true) && \
	if [ -n "$${images}" ]; then \
	    docker rmi $${images}; \
	fi

