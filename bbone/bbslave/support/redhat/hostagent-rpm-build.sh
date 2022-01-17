#!/bin/sh

# Simple script that gets packaged as part of hostagent rpm tarball and executed inside the DU to generate rpm dynamically per customer-specific parameters

set -v

RPMBUILD_DIR="$1"
TARBALL_EXPANDED_LOCATION="$2"
HOST_IP="$3"
VERSION="$4"
RELEASE="$5"
HYPERVISOR_TYPE="$6"
AMQP_USER="$7"
AMQP_PASS="$8"
DU_IS_CONTAINER="$9"
CERT_VERSION="${10}"
HOSTAGENT_SKIP_CERTS="${11}"

# The directory where the build is done
SPEC_FILE_DIR=`mktemp -d -t pf9-XXX`

# Remove the .spec, the hostagent-rpmbuild.sh file from the BUILD_DIR
mv $TARBALL_EXPANDED_LOCATION/hostagent.spec $SPEC_FILE_DIR/hostagent.spec
mv $TARBALL_EXPANDED_LOCATION/hostagent-nocert.spec $SPEC_FILE_DIR/hostagent-nocert.spec
mv $TARBALL_EXPANDED_LOCATION/hostagent-rpm-build.sh $SPEC_FILE_DIR/hostagent-rpm-build.sh

sed -i -e "s/CHANGE_TO_YOUR_BROKER_IP/$HOST_IP/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf
sed -i -e "s/CHANGE_TO_YOUR_AMQP_USER/$AMQP_USER/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf
sed -i -e "s/CHANGE_TO_YOUR_AMQP_PASS/$AMQP_PASS/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf
sed -i -e "s/hypervisor_type.*/hypervisor_type=$HYPERVISOR_TYPE/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf
sed -i -e "s/CHANGE_TO_YOUR_DU_IS_CONTAINER_FLAG/$DU_IS_CONTAINER/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf
sed -i -e "s/CHANGE_TO_YOUR_CERT_VERSION/$CERT_VERSION/" $TARBALL_EXPANDED_LOCATION/etc/pf9/hostagent.conf

if [ -z "${HOSTAGENT_SKIP_CERTS}" ]; then
    rpmbuild -bb --define "_topdir $RPMBUILD_DIR" --define "_src_dir $TARBALL_EXPANDED_LOCATION"  --define "_version $VERSION" --define "_release $RELEASE" $SPEC_FILE_DIR/hostagent.spec
else
    rpmbuild -bb --define "_topdir $RPMBUILD_DIR" --define "_src_dir $TARBALL_EXPANDED_LOCATION"  --define "_version $VERSION" --define "_release $RELEASE" $SPEC_FILE_DIR/hostagent-nocert.spec
fi

cp $SPEC_FILE_DIR/hostagent-rpm-build.sh $TARBALL_EXPANDED_LOCATION/hostagent-rpm-build.sh
cp $SPEC_FILE_DIR/hostagent.spec $TARBALL_EXPANDED_LOCATION/hostagent.spec
cp $SPEC_FILE_DIR/hostagent-nocert.spec $TARBALL_EXPANDED_LOCATION/hostagent-nocert.spec
rm -rf $SPEC_FILE_DIR
