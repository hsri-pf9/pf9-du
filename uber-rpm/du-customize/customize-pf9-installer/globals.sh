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
JQ="/opt/pf9/hostagent/bin/jq"

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

# List of Exit codes
CONTROLLER_ADRESS_MISSING=31
CONTROLLER_USER_MISSING=32
CONTROLLER_PROJECTNAME_MISSING=33
CONTROLLER_PASSWORD_MISSING=34
KEYSTONE_REQUEST_FAILED=35
KEYSTONE_TOKEN_MISSING=36
NTPD_INSTALL_FAILED=41
NTPD_FAILED_TO_START=42
CHRONY_INSTALL_FAILED=43
CHRONY_FAILED_TO_START=44
ARCHITECTURE_NOT_SUPPORTED=51
OS_NOT_SUPPORTED=52
CORRUPT_SUDOERS_FILE=53
IMPORTANT_PORT_OCCUPIED=54
CONNECTION_FAILED=55
CONNECTION_FAILED_VIA_PROXY=56
PKG_MANAGER_MISSING=57
PF9_PACKAGES_PRESENT=58
HOSTAGENT_DEPENDANCY_INSTALLATION_FAILED=61
DOWNLOAD_NOCERT_ARGUMENT_MISSING=71
PACKAGE_LIST_DOWNLOAD_FAILED=72
PACKAGE_DOWNLOAD_FAILED=73
HOSTAGENT_PKG_INSTALLATION_FAILED=81
PROXY_SETUP_FAILED=90
UPDATE_CONFIG_FAILED=100
VOUCH_ARGUMENT_MISSING=111
HOST_CERTS_SCRIPT_FAILED=112
VMWARE_INSALL_FAILED=121
SYSTEMCTL_FAILED_TO_START_COMMS=131
COMMS_NOT_UP=132
SYSTEMCTL_FAILED_TO_START_SIDEKICK=133
SIDEKICK_NOT_UP=134
SYSTEMCTL_FAILED_TO_START_HOSTAGENT=135
HOSTAGENT_NOT_UP=136
HOSTAGENT_NOT_RUNNING=137
HOSTAGENT_FILES_MISSING=138
COMMS_NOT_RUNNING=139
PARAMS_MISSING=141
CREDS_NOT_NEEDED=142
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
