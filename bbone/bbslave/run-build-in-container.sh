#!/bin/bash

set -x -e

groupadd --gid ${PARENT_GID} pf9
useradd --gid ${PARENT_GID} --uid ${PARENT_UID} -m pf9
mkdir -p /home/pf9/bin
cp /root/gpg-shim /home/pf9/bin/gpg
cp -R /dockstage/.{gnupg,gpgpass,rpmmacros} /home/pf9
chown -R pf9:pf9 /home/pf9 /buildroot

sudo -u pf9 make -C /buildroot/pf9-du/bbone/bbslave/support/redhat hostagent-tarball \
            TARGET_DISTRO=redhat
