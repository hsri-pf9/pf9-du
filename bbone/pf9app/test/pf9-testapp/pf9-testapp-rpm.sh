#!/bin/sh

# Prerequisites to run this script
# 1. Install mock. #yum install mock (note that you need to have epel repo in
# your repo list
# 2. Add your username to mock group. #usermod -a -G mock  your_username
# 3. Logout and login to a new session to be able to use mock
#
# Usage: pf9-testapp-rpm.sh <path to spec file>
#
# Output rpm will be in <codebase>/build/pf9-testapp/rpmbuild/ directory

set -e

RPMSPEC="$1"
# Get absolute path for the base dir
BASEDIR=$(cd "$(dirname "$1")"; pwd)
BUILD_ROOT="$BASEDIR"/../../../../build/pf9-testapp
CONFIGUTILS_ROOT="$BASEDIR"/../../../../lib/configutils/configutils
SRC_STAGE_ROOT="$BUILD_ROOT"/src
SRC_BUILD_ROOT="$BUILD_ROOT"/srcbuild
RPM_BUILD_ROOT="$BUILD_ROOT"/rpmbuild

rm -rf "$BUILD_ROOT"
mkdir -p "$BUILD_ROOT"
mkdir -p "$SRC_STAGE_ROOT"
mkdir -p "$SRC_BUILD_ROOT"
mkdir -p "$RPM_BUILD_ROOT"

cp "$BASEDIR"/* "$SRC_STAGE_ROOT"
cp "$CONFIGUTILS_ROOT"/*.py "$SRC_STAGE_ROOT"


mock --buildsrpm --sources "$SRC_STAGE_ROOT" --spec "$SRC_STAGE_ROOT"/pf9-testapp.spec --resultdir "$SRC_BUILD_ROOT"

mock --rebuild --resultdir "$RPM_BUILD_ROOT" "$SRC_BUILD_ROOT"/pf9-testapp-1.0-1.src.rpm
