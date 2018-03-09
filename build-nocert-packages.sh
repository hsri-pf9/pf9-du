#!/usr/bin/env bash

SRCROOT=$(cd $(dirname $0); pwd)

make -C $SRCROOT/uber-rpm installer-nocert
make -C $SRCROOT/bbone/bbslave/support/redhat hostagent-rpm-nocert
make -C $SRCROOT/bbone/bbslave/support/debian hostagent-deb-nocert
