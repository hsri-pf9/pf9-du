#!/bin/python
# Copyright (c) 2015 Platform9 Systems Inc.

# All global variables should be set here

# always ask if user wants to configure proxy settings
ASK_PROXY="true"
SETUP_PROXY="true"
TTY_AVAILABLE="true"
SKIP_OS_CHECK="false"
VMWARE="false"
PROXY_HOST=""
PROXY_PORT=""
JSON_TOOL="jsontool.py"

# to be replaced by the build script
DU_FQDN=__DU_FQDN__

PF9_COMMS_PROXY_CONF="/etc/pf9/comms_proxy_cfg.json"
HOSTAGENT_DIR="/var/opt/pf9/hostagent"
DESIRED_APPS="desired_apps.json"

# if installation fails, we write some
# system information here
SYSTEM_INFO_LOG="platform9-system-info.log"
SUPPORT_BUNDLE="platform9-log-bundle.tar.gz"

# directories to tar up in case
# installation fails
SUPPORT_DIRS=("/var/log/pf9" \
              "/var/opt/pf9" \
              "/etc/opt/pf9")

# For RHEL 7+, this avoids calls to sysctl,
# which breaks the init scripts.
export SYSTEMCTL_SKIP_REDIRECT=1

# Check if /sbin is in the path
echo $PATH | grep "/sbin" -q

if [[ $? != "0" ]]; then
    echo "Cannot find 'sbin' in the \$PATH. Exiting..."
    exit 1
fi

# Check if the service command exists at the very least
which service > /dev/null 2>&1
if [[ $? != "0" ]]; then
    echo "Cannot find the command 'service' in $PATH. Exiting..."
    exit 1
fi

tty -s
if [[ $? != "0" ]]; then
    echo "No TTY available. Skipping all prompts..."
    TTY_AVAILABLE="false"
fi
