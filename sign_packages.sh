#!/bin/sh

echo "SIGN_PKG_VAL = ${SIGN_PACKAGES}"
if [ "x${SIGN_PACKAGES}" = "x1" ]; then
    expect $(dirname $0)/du.expect $@
fi
