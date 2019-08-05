#!/bin/bash
set -e

# Arguments to the postrm script:
script_name=$0
script_step=$1
# new_version=$2

# The cache clean up will be done with uninstall and upgrade
# of the hostagent.
rm -rf "/var/opt/pf9/hostagent"

case "$script_step" in
    # Remove the apps cache in case of an uninstall
    remove | purge | disappear)
        rm -rf "/var/cache/pf9apps"
        pkill pf9-sidekick || true
        ;;
esac
