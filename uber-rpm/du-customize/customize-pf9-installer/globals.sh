#!/bin/python
# Copyright (c) 2015 Platform9 Systems Inc.

# All global variables should be set here

# always ask if user wants to configure proxy settings
ASK_PROXY="true"
SETUP_PROXY="true"
TTY_AVAILABLE="true"
SKIP_OS_CHECK="false"
ASK_NTPD="true"
INSTALL_NTPD="true"
VMWARE="false"
PROXY_URL=""
PROXY_PROTOCOL="http"
PROXY_HOST=""
PROXY_PORT=""
PROXY_USER=""
PROXY_PASS=""
JSON_TOOL="jsontool.py"

# to be replaced by the build script
DU_FQDN=__DU_FQDN__

PF9_COMMS_PROXY_CONF="/etc/pf9/comms_proxy_cfg.json"
PF9_HOSTAGENT_ENV_FILE="/opt/pf9/hostagent/pf9-hostagent.env"
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

# Use systemctl with no-pager option because some automation tools
# use tty mode which can trigger systemctl to work in pager mode
# causing commands to hang waiting for users to quit the pager.
# More details: https://www.freedesktop.org/software/systemd/man/systemctl.html#%24SYSTEMD_PAGER
SYSTEMCTL_CMD="systemctl --no-pager"

# Check if /sbin is in the path
echo $PATH | grep "/sbin" -q

if [[ $? != "0" ]]; then
    echo "Cannot find 'sbin' in the \$PATH. Exiting..."
    exit 1
fi

# Check if the service command exists at the very least
which systemctl > /dev/null 2>&1
if [[ $? != "0" ]]; then
    echo "Cannot find the command 'systemctl' in $PATH. Exiting..."
    exit 1
fi

tty -s
if [[ $? != "0" ]]; then
    echo "No TTY available. Skipping all prompts..."
    TTY_AVAILABLE="false"
fi
