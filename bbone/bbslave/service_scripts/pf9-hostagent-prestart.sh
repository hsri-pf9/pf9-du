#!/bin/bash

mkdir -p /tmp/python-eggs
chown pf9:pf9group /tmp/python-eggs

# create cache folder and set owner before hostagent runs
mkdir -p /opt/pf9/cache
chown -R pf9:pf9group /opt/pf9/cache

. /etc/os-release

if [[ "$ID" == "ubuntu" ]]
then
    if [[ "${VERSION_ID%.*}" == "16" ]]
    then
        ln -sf /usr/lib/python3/dist-packages/apt_inst.cpython-35m-x86_64-linux-gnu.so /opt/pf9/python/lib/python3.6/apt_inst.so
        ln -sf /usr/lib/python3/dist-packages/apt_pkg.cpython-35m-x86_64-linux-gnu.so /opt/pf9/python/lib/python3.6/apt_pkg.so
    elif [[ "${VERSION_ID%.*}" == "18" ]]
    then
        ln -sf /usr/lib/python3/dist-packages/apt_inst.cpython-36m-x86_64-linux-gnu.so /opt/pf9/python/lib/python3.6/apt_inst.so
        ln -sf /usr/lib/python3/dist-packages/apt_pkg.cpython-36m-x86_64-linux-gnu.so /opt/pf9/python/lib/python3.6/apt_pkg.so
    fi
fi
