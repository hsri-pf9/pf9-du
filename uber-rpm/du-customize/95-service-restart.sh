#!/bin/bash

#
# Copyright (c) 2014, Platform 9 Systems Inc. All rights reserved.
#

# Restart services post customization

SERVICES="openstack-nova-conductor pf9-resmgr"

set -e -x

for service in $SERVICES; do
    echo "Stopping " $service
    sudo service $service stop
done

for service in $SERVICES; do
    echo "Starting " $service
    sudo service $service start
done

