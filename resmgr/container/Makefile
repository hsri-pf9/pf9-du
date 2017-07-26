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

DISTS = $(RESMGR_DIST) $(BBLIB_DIST) $(BBMASTER_DIST) $(CONFIGUTILS_DIST) \
        $(NOTIFIER_DIST) $(RABBIT_DIST)

dist: $(DISTS)

# FIXME - Do NOT copy paste the logic below if we add deb support. Come up with
# a way to parameterize it!

HOSTAGENT_RPM = $(BLDROOT)/hostagent/redhat-nocert/rpm-build/RPMS/x86_64/pf9-hostagent-$(PF9_VERSION)-$(BUILD_NUMBER).$(GITHASH).x86_64.rpm
INSTALLER_SCRIPT = $(SRCROOT)/uber-rpm/build/platform9-install-redhat.sh

COMMS_RPM ?= $(shell find $(ARTIFACTS) -name pf9-comms*.rpm)
ifeq ($(wildcard $(COMMS_RPM)),)
    $(error No comms rpm available. Either make sure the file is in \
      $(ARTIFACTS), or set env COMMS_RPM to the path of the file)
endif

PACKAGELIST = $(STAGE)/opt/pf9/www/private/nocert-packagelist.rpm
PACKAGELIST_LINES = etc/pf9/certs/hostagent/cert.pem \
                    etc/pf9/certs/hostagent/key.pem \
                    etc/pf9/certs/ca/cert.pem \
                    etc/pf9/hostagent.conf \
                    $(notdir $(HOSTAGENT_RPM)) \
                    $(notdir $(COMMS_RPM))

$(DISTS):
	cd $(SETUP_ROOT) && \
	rm -f dist/* && \
	python setup.py sdist && \
	cp -vf dist/* $@

$(HOSTAGENT_RPM):
	make -C $(SRCROOT)/bbone/bbslave/support/redhat hostagent-rpm-nocert

$(INSTALLER_SCRIPT):
	make -C $(SRCROOT)/uber-rpm installer-nocert

stage: dist $(HOSTAGENT_RPM) $(INSTALLER_SCRIPT) $(PACKAGELIST_RPM)
	cp -rv $(SRCROOT)/resmgr/container/* $(STAGE)/
	cp -v $(SRCROOT)/resmgr/upper-constraints.txt $(STAGE)/
	private=$(STAGE)/opt/pf9/www/private && \
	mkdir -p $${private} && \
	cp -v $(HOSTAGENT_RPM) $(INSTALLER_SCRIPT) $(COMMS_RPM) $${private} && \
	rm -fv $(PACKAGELIST) && \
	for line in $(PACKAGELIST_LINES); do \
	    echo $${line} >> $(PACKAGELIST); \
	done && \
	echo "$(PACKAGELIST):" && \
	cat $(PACKAGELIST)

image: stage
	docker build -t 514845858982.dkr.ecr.us-west-1.amazonaws.com/pf9-resmgr $(STAGE)

# This assumes that credentials for the aws tool are configured, either in
# ~/.aws/config or in AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY
push: image
	docker push 514845858982.dkr.ecr.us-west-1.amazonaws.com/pf9-resmgr || \
	(aws ecr get-login --region=us-west-1 |sh && \
	 docker push 514845858982.dkr.ecr.us-west-1.amazonaws.com/pf9-resmgr)

clean:
	rm -rf $(STAGE)
	images=$$(docker images -q -f dangling=true) && \
	if [ -n "$${images}" ]; then \
	    docker rmi $${images}; \
	fi

