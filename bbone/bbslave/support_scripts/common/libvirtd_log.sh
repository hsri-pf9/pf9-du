#!/bin/bash

set -x

sudo tar -cf /var/log/pf9/libvirtd.tar /var/log/libvirt
sudo chown pf9:pf9group /var/log/pf9/libvirtd.tar
sudo cp -f /var/log/dmesg* /var/log/pf9/ || :
sudo cp -f /var/log/syslog* /var/log/pf9/ || :
sudo cp -f /var/log/messages* /var/log/pf9/ || :
sudo chown pf9:pf9group /var/log/pf9/dmesg* || :
sudo chown pf9:pf9group /var/log/pf9/syslog* || :
sudo chown pf9:pf9group /var/log/pf9/messages* || :
