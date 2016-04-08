#!/usr/bin/env bash

# $1 = desired pf9 home directory
# $2 = optional sudo command (i.e. 'sudo' or blank)
function create_pf9_homedir_if_absent() {
    local homedir=$1
    local sudocmd=$2
    if [ ! -e ${homedir} ]; then
        # Original home dir creation failed, probably due to IAAS-4714
        echo creating pf9 home directory
        ${sudocmd} mkdir -p ${homedir}
        # Do chown now so that, if running as pf9 from
        # /opt/pf9/comms/utils/forward_ssh.sh, we can do the cp and touch
        # without sudo privileges
        ${sudocmd} chown -R pf9:pf9group ${homedir}
        cp /etc/skel/.bash* ${homedir}
        touch ${homedir}/.iaas-4714
        # Do this again because we might be running as root (if invoked from
        # yum post-install script), in which case the copied files are still
        # owned by root.
        ${sudocmd} chown -R pf9:pf9group ${homedir}
    fi
}

