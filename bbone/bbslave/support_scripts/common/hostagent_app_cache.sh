#!/bin/bash

set -x

find /var/cache/pf9apps -type f -print0 | xargs -0 md5sum

find /var/cache/pf9apps -type f -print0 | xargs -0 ls -al

