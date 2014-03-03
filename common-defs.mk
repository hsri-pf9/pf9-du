# Common definitions for our makefiles

export SRC_ROOT := $(abspath $(dir $(CURDIR)/$(word $(words $(MAKEFILE_LIST)),$(MAKEFILE_LIST))))
export BUILD_ROOT := $(SRC_ROOT)/build
