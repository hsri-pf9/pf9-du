# Common definitions for our makefiles

# SRC_ROOT = absolute path of this file i.e. the pf9-du folder
export SRC_ROOT := $(abspath $(dir $(CURDIR)/$(word $(words $(MAKEFILE_LIST)),$(MAKEFILE_LIST))))
# BUILD_ROOT = pf9-du/build
export BUILD_ROOT := $(SRC_ROOT)/build
