#!/usr/bin/env bash

# Copyright (c) 2017 Platform9 Systems Inc.

#
# Print a keystone token given the following variables:
#
# DU_FQDN: address of the DU. keystone auth url is expected to be at
#          https://$DU_FQDN/keystone/v3
# OS_USERNAME: keystone username
# OS_PASSWORD: keystone password
# OS_TENANT_NAME: project name for the requested token
#
function keystone_token() {
    local url="https://$DU_FQDN/keystone/v3/auth/tokens"
    local content_type="Content-Type: application/json"
    local auth
    local scope
    read -d '' auth <<END_DATA
         "auth": {
             "identity": {
                 "methods": ["password"],
                 "password": {
                     "user": {
                         "name": "$OS_USERNAME",
                         "domain": {"id": "default"},
                         "password": "$OS_PASSWORD"
                     }
                 }
             }
END_DATA
    if [ -z "$DONT_ASK_PROJECT" ]; then
        read -d '' scope <<END_DATA
                 ,"scope": {
                     "project": {
                         "name": "$OS_TENANT_NAME",
                         "domain": { "id": "default" }
                     }
                 }
END_DATA
    fi
    local resp=`curl ${CURL_INSECURE} -si -XPOST -H "$content_type" -d "{${auth}${scope}}}" "$url"`
    local token=`echo $resp |sed -n 's/^.*X-Subject-Token: \([^\r\n\t ]*\).*/\1/I p'`
    if [ -z "${token}" ]; then
        echo "Failed to authenticate with the keystone server on $DU_FQDN, response:" >&2
        echo ${resp} >&2
        return 1
    else
        echo ${token}
    fi
}
