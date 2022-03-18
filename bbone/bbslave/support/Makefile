#! vim noexpandtab
# Copyright (C) 2014 Platform 9 Systems, Inc.
#
# Usage: make hostagent-tarball-rpm-debian
#        make hostagent-tarball-rpm-redhat
#

include ../../../common-defs.mk

BUILD_DIR := $(BUILD_ROOT)/hostagent
HOSTAGENT_REDHAT_TARGET ?= hostagent-redhat

hostagent-tarball-redhat:
	(cd redhat && make hostagent-tarball)

hostagent-tarball-rpm-only-redhat:
	(cd redhat && make hostagent-tarball-rpm-redhat)

hostagent-tarball-rpm-redhat:
	(cd redhat && make $(HOSTAGENT_REDHAT_TARGET))

hostagent-tarball-debian:
	(cd debian && make hostagent-tarball)

hostagent-tarball-rpm-only-debian:
	(cd debian && make hostagent-tarball-rpm-debian)

hostagent-tarball-rpm-debian:
	(cd debian && make hostagent-tarball-rpm-debian)

unit-test:
	(cd redhat && make unit-test)

clean:
	(cd redhat && make clean)
	(cd debian && make clean)

	rm -rf $(BUILD_DIR)
