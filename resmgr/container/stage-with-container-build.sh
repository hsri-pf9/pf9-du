#!/bin/bash

set -xue

cd /buildroot/pf9-du/resmgr/container && make --max-load=$(nproc) stage-with-py-build-container
