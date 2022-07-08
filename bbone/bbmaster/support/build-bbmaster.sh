#!/bin/bash
set -eo pipefail # in case of a command pipeline, allow non zero return code to be captured
[ -n "${BASH_DEBUG}" ] && set -x # setting BASH_DEBUG lets us debug shell bugs in this script

REPO_DIR=$(cd $(dirname $0); git rev-parse --show-toplevel)
WORKSPACE=$(cd ${REPO_DIR}/..; pwd)
BUILD_DIR=${REPO_DIR}/build

BUILD_IMAGE=artifactory.platform9.horse/docker-local/py39-build-image:latest # can change to 5.6.0 if need be

echo Building pf9-bbmaster RPM ...
docker run  --rm -i \
    -u $(id -u):$(id -g) \
    -e PF9_VERSION=${PF9_VERSION:=1.3.0} \
    -e BUILD_NUMBER=${BUILD_NUMBER:=0} \
    -e GITHASH=${GITHASH} \
    -v ${WORKSPACE}/pf9-du:/src/pf9-du \
    -v /etc/passwd:/etc/passwd \
    -w /src/pf9-du/bbone/bbmaster/support \
    ${BUILD_IMAGE} /bin/bash -c "make rpm && make unit-test"
