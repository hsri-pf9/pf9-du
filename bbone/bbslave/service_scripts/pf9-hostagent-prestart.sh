#!/bin/bash

mkdir -p /tmp/python-eggs
chown pf9:pf9group /tmp/python-eggs

. /etc/os-release

if [[ "$ID" == "ubuntu" && "$VERSION_ID" == "16.04" ]]
then
    ln -sf /usr/lib/python2.7/dist-packages/apt_inst.x86_64-linux-gnu.so /opt/pf9/python/lib/python2.7/apt_inst.so
    ln -sf /usr/lib/python2.7/dist-packages/apt_pkg.x86_64-linux-gnu.so /opt/pf9/python/lib/python2.7/apt_pkg.so
fi
