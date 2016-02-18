#!/bin/bash
set -e -x

NAME=pf9-du
PF9_VERSION=${PF9_VERSION:-0.0.7}

cd $(dirname $0)
SRCROOT=$(pwd)

# All intermediate and final build outputs go here
BLDROOT=$SRCROOT/build
rm -rf $BLDROOT
mkdir -p $BLDROOT

# Generate the spec file
cd $BLDROOT
# BUILD_NUMBER is pre-defined in TeamCity builds
BUILD_NUMBER=${BUILD_NUMBER:-0}
sed -e "s/__BUILDNUM__/$BUILD_NUMBER/" \
    -e "s/__GITHASH__/$(git rev-parse --short HEAD)/" \
    -e "s/__VERSION__/$PF9_VERSION/" \
    $SRCROOT/$NAME.spec > $NAME.spec

# Generate $NAME-$PF9_VERSION.tar.gz from source files in git
rm -rf $NAME-$PF9_VERSION
mkdir -p $NAME-$PF9_VERSION/opt/pf9/du-customize
mkdir -p $NAME-$PF9_VERSION/etc/pf9
cp -a $SRCROOT/du-customize $NAME-$PF9_VERSION/opt/pf9/
cp -a $SRCROOT/controller/etc/global.conf $NAME-$PF9_VERSION/etc/pf9
tar zcf $NAME-$PF9_VERSION.tar.gz $NAME-$PF9_VERSION
rm -rf $NAME-$PF9_VERSION

# Now build the RPMs
MOCK="/usr/bin/mock -r epel-7-x86_64"
$MOCK --buildsrpm --spec $NAME.spec --sources . --resultdir SRPMS
$MOCK --rebuild SRPMS/*.src.rpm --resultdir RPMS
${SRCROOT}/../sign_packages.sh RPMS/pf9-du*.rpm
