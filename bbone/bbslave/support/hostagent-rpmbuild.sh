#!/bin/sh

# Simple script that gets packaged as part of hostagent rpm tarball and executed inside the DU to generate rpm dynamically per customer-specific parameters

set -v
RPMBUILD_DIR="$1"
TARBALL_EXPANDED_LOCATION="$2"
VERSION="$3"
HOST_IP="$4"

# The directory where the build is done
SPEC_FILE_DIR=`mktemp -d -t pf9-XXX`

# Remove the .spec, the hostagent-rpmbuild.sh file from the BUILD_DIR
mv $TARBALL_EXPANDED_LOCATION/hostagent.spec $SPEC_FILE_DIR/hostagent.spec
mv $TARBALL_EXPANDED_LOCATION/hostagent-rpmbuild.sh $SPEC_FILE_DIR/hostagent-rpmbuild.sh

sed -i -e "s/CHANGE_TO_YOUR_BROKER_IP/$HOST_IP/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf


rpmbuild -bb --define "_topdir $RPMBUILD_DIR" --define "_src_dir $TARBALL_EXPANDED_LOCATION"  --define "_version $VERSION"  $SPEC_FILE_DIR/hostagent.spec

rm -rf $SPEC_FILE_DIR
