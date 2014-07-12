#! vim noexpandtab
# Copyright (C) 2014 Platform 9 Systems, Inc.
#
# Usage: make hostagent-tarball-rpm-debian
#        make hostagent-tarball-rpm-redhat
#

include ../../../common-defs.mk

BUILD_DIR := $(BUILD_ROOT)/hostagent

hostagent-tarball-rpm-redhat:
	(cd redhat; make hostagent-tarball-rpm-redhat; cd ..)

hostagent-tarball-rpm-debian:
	(cd debian; make hostagent-tarball-rpm-debian; cd ..)

unit-test:
	(cd redhat; make unit-test; cd ..)

clean:
	(cd redhat; make clean; cd ..)
	(cd debian; make clean; cd ..)

	rm -rf $(BUILD_DIR)

