#!/bin/sh

if [ "x${SKIP_SIGNING}" != "x1" ]; then
    expect $(dirname $0)/du.expect $@
fi
