#!/bin/sh

# Simple script that gets packaged as part of hostagent rpm tarball and executed
# inside the DU to generate a deb package dynamically per customer-specific
# parameters.
#
# Requires: fpm

set -v

RPMBUILD_DIR="$1"
TARBALL_EXPANDED_LOCATION="$2"
HOST_IP="$3"
VERSION="$4"
RELEASE="$5"

# The directory where the build is done
SPEC_FILE_DIR=`mktemp -d -t pf9-XXX`
PRIVATE_FILES_DIR=/opt/pf9/www/private
DEB_FILE_NAME=pf9-hostagent-$VERSION-$RELEASE.x86_64.deb
DEB_FILE=$PRIVATE_FILES_DIR/$DEB_FILE_NAME
HOST_AGENT_DEB_SYMLINK=pf9-hostagent.x86_64.deb

# Remove after-install.sh and hostagent-deb-build from the BUILD_DIR
mv $TARBALL_EXPANDED_LOCATION/after-install.sh $SPEC_FILE_DIR
mv $TARBALL_EXPANDED_LOCATION/hostagent-deb-build.sh $SPEC_FILE_DIR

sed -i -e "s/CHANGE_TO_YOUR_BROKER_IP/$HOST_IP/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf

mkdir -p $PRIVATE_FILES_DIR

fpm -t deb -s dir --provides "pf9-hostagent" --provides "pf9-bbslave" -d "sudo" -d "python-setuptools" --after-install $SPEC_FILE_DIR/after-install.sh -p $DEB_FILE -n pf9-hostagent -C $TARBALL_EXPANDED_LOCATION .

# Symlink the rpm to a well known location
pushd $PRIVATE_FILES_DIR
ln -sf $DEB_FILE_NAME $HOST_AGENT_DEB_SYMLINK
popd
