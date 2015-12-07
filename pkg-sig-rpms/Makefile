SOURCE_SHA2SUMS=\
7ad5e4466da1f59ce95111432345a4d4beeda602f8c28be6e09f79e32043916a  build/SOURCES/Config-File-1.50.tar.gz\n\
fee1c098bee5a3f726219d8ec59a767d44a7e0a0bfe81b7f207e61ce6e20b7c2  build/SOURCES/dpkg-sig_0.13.1+nmu2.tar.gz\n\



build:
	mkdir build

rpmenv: build
	mkdir -p build/{RPMS/noarch,RPMS/x86_64,SRPMS,SPECS,BUILDROOT,SOURCES}

sources: rpmenv
	spectool -g -S -C build/SOURCES perl-Config-File.spec
	spectool -g -S -C build/SOURCES dpkg-sig.spec
	# lol rpm doesn't have built-in support for source verification
	echo -ne "$(SOURCE_SHA2SUMS)" | sha256sum -c -

perl-Config-rpms: build rpmenv sources
	rpmbuild --define "_topdir $(shell pwd)/build" -bb perl-Config-File.spec

dpkg-sig-rpms: build rpmenv sources
	rpmbuild --define "_topdir $(shell pwd)/build" -bb dpkg-sig.spec

rpms: perl-Config-rpms dpkg-sig-rpms

clean:
	rm -rf build
