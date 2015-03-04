#!/bin/python
# Copyright (c) 2015 Platform9 Systems Inc.

# All global variables should be set here

# always ask if user wants to configure proxy settings
ASK_PROXY="true"
SETUP_PROXY="true"
PROXY_HOST=""
PROXY_PORT=""
JSON_TOOL="jsontool.py"

PF9_COMMS_CONF="/etc/pf9/comms.json"
HOSTAGENT_DIR="/var/opt/pf9/hostagent"
DESIRED_APPS="desired_apps.json"

# if installation fails, we write some
# system information here
SUPPORT_FILE="system-info"
SUPPORT_BUNDLE="platform9-support-bundle.tar.gz"

# directories to tar up in case
# installation fails
SUPPORT_DIRS=("/var/log/pf9" \
              "/var/opt/pf9" \
              "/etc/opt/pf9")

