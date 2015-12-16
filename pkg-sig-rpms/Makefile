SOURCE_SHA2SUMS=\
ee446635e246bc6575822b353d59f9f409e3ac9b1e139d887cf318adc814053c  build/SOURCES/debsig-verify_0.8.tar.gz\n\
bae1e8bb28a6ab921e77dcadb1fc65f2058f4ff50255d090baa42cf918f760cc  build/SOURCES/debsigs_0.1.18.tar.xz\n\


build:
	mkdir build

rpmenv: build
	mkdir -p build/{RPMS/noarch,RPMS/x86_64,SRPMS,SPECS,BUILDROOT,SOURCES}

sources: rpmenv
	./sync_sources.sh debsigs.spec build/SOURCES 1
	./sync_sources.sh debsig-verify.spec build/SOURCES 1
	echo -ne "$(SOURCE_SHA2SUMS)" | sha256sum -c -

debsig-verify-patches: rpmenv
	cp pf9-xmltok-to-expat.patch build/SOURCES

debsigs-rpms: build rpmenv sources
	rpmbuild --define "_topdir $(shell pwd)/build" -bb debsigs.spec

debsig-verify-rpms: build rpmenv sources debsig-verify-patches
	rpmbuild --define "_topdir $(shell pwd)/build" -bb debsig-verify.spec

rpms: debsigs-rpms debsig-verify-rpms

clean:
	rm -rf build
