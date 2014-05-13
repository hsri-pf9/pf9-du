#!/bin/bash
set -e -x

NAME=pf9-du
VERSION=1.0.0

cd $(dirname $0)
SRCROOT=$(pwd)

# All intermediate and final build outputs go here
BLDROOT=$SRCROOT/build
rm -rf $BLDROOT
mkdir -p $BLDROOT

# Generate the spec file
cd $BLDROOT
# BUILD_NUMBER is pre-defined in TeamCity builds
test -z "$BUILD_NUMBER" && BUILD_NUMBER=0
sed -e "s/__BUILDNUM__/$BUILD_NUMBER/" \
    -e "s/__GITHASH__/$(git rev-parse --short HEAD)/" \
    $SRCROOT/$NAME.spec > $NAME.spec

# Generate $NAME-$VERSION.tar.gz from source files in git
rm -rf $NAME-$VERSION
mkdir -p $NAME-$VERSION/opt/pf9/du-customize
mkdir -p $NAME-$VERSION/etc/pf9
mkdir -p $NAME-$VERSION/etc/rabbitmq
cp -a $SRCROOT/du-customize $NAME-$VERSION/opt/pf9/
cp -a $SRCROOT/controller/etc/global.conf $NAME-$VERSION/etc/pf9
cp -a $SRCROOT/du-install/rabbitmq.config $NAME-$VERSION/etc/rabbitmq
tar zcf $NAME-$VERSION.tar.gz $NAME-$VERSION
rm -rf $NAME-$VERSION

# Now build the RPMs
MOCK="/usr/bin/mock -r epel-6-x86_64"
$MOCK --buildsrpm --spec $NAME.spec --sources . --resultdir SRPMS
$MOCK --rebuild SRPMS/*.src.rpm --resultdir RPMS
