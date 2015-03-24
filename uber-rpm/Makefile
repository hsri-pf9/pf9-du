# Makefile for uber RPM for DU

build:
	./build-rpm.sh

unit-test:
	(cd "./du-customize/customize-pf9-installer/tests/" && bash ./test_check_os_version.sh)

clean:
	rm -rf build

.PHONY: build clean
