#!/bin/sh

# Simple script that gets packaged as part of hostagent rpm tarball and executed
# inside the DU to generate a deb package dynamically per customer-specific
# parameters.
#
# Requires: fpm

set -e
set -v

DEBBUILD_DIR="$1"
TARBALL_EXPANDED_LOCATION="$2"
HOST_IP="$3"
VERSION="$4"
RELEASE="$5"
AMQP_USER=$6
AMQP_PASS=$7
DU_IS_CONTAINER="$8"
CERT_VERSION="$9"

# The directory where the build is done
SPEC_FILE_DIR=`mktemp -d -t pf9-XXX`
DEB_FILE_NAME=pf9-hostagent-$VERSION-$RELEASE.x86_64.deb
DEB_FILE=$DEBBUILD_DIR/$DEB_FILE_NAME
HOST_AGENT_DEB_SYMLINK=pf9-hostagent.x86_64.deb

# Remove after-install.sh and hostagent-deb-build from the BUILD_DIR
mv $TARBALL_EXPANDED_LOCATION/after-install.sh $SPEC_FILE_DIR
mv $TARBALL_EXPANDED_LOCATION/after-remove.sh $SPEC_FILE_DIR
mv $TARBALL_EXPANDED_LOCATION/before-remove.sh $SPEC_FILE_DIR
mv $TARBALL_EXPANDED_LOCATION/hostagent-deb-build.sh $SPEC_FILE_DIR

sed -i -e "s/CHANGE_TO_YOUR_BROKER_IP/$HOST_IP/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf
sed -i -e "s/CHANGE_TO_YOUR_AMQP_USER/$AMQP_USER/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf
sed -i -e "s/CHANGE_TO_YOUR_AMQP_PASS/$AMQP_PASS/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf
sed -i -e "s/CHANGE_TO_YOUR_DU_IS_CONTAINER_FLAG/$DU_IS_CONTAINER/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf
sed -i -e "s/CHANGE_TO_YOUR_CERT_VERSION/$CERT_VERSION/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf

fpm -t deb -s dir --provides "pf9-hostagent" --provides "pf9-bbslave" -d "sudo" -d "procps" \
        -d "python-setuptools" -d "iptables-persistent" -d "python-apt" --after-install $SPEC_FILE_DIR/after-install.sh \
        --after-remove $SPEC_FILE_DIR/after-remove.sh --before-remove $SPEC_FILE_DIR/before-remove.sh \
        --license "Commercial" --architecture all --url "http://www.platform9.net" --vendor Platform9 \
        --config-files /etc/pf9/hostagent.conf \
        -v $VERSION-$RELEASE -p $DEB_FILE -n pf9-hostagent --description "Platform9 host agent" \
        --force -C $TARBALL_EXPANDED_LOCATION .

