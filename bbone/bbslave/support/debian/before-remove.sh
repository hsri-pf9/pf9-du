set -e

# Arguments to the prerm script:
#script_name=$0
script_step=$1
new_version=$2

if [ "$script_step" = "remove" ]; then
    service pf9-hostagent stop > /dev/null 2>&1
    update-rc.d -f pf9-hostagent remove > /dev/null 2>&1
fi
