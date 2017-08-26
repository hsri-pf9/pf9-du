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
    local body
    read -d '' body <<END_DATA
         {"auth": {
             "identity": {
                 "methods": ["password"],
                 "password": {
                     "user": {
                         "name": "$OS_USERNAME",
                         "domain": {"id": "default"},
                         "password": "$OS_PASSWORD"
                     }
                 }
             },
             "scope": {
                 "project": {
                     "name": "$OS_TENANT_NAME",
                     "domain": { "id": "default" }
                 }
             }
         }}
END_DATA
    local resp=`curl ${CURL_INSECURE} -si -XPOST -H "$content_type" -d "$body" "$url"`
    local result=$?
    if [ $result -eq 0 ]; then
        local code=`echo $resp |cut -f 2 -d ' '`
        if [ -z "$code" ]; then
            echo "Bad response from keystone server: $resp" >&2
            return 1
        elif [ $code -ne 201 ]; then
            echo "Bad response from keystone server:" >&2
            echo "Code: $code" >&2
            echo "Response: $resp" >&2
            return 1
        else
            echo $resp |sed -n 's/^.*X-Subject-Token: \([^\r\n\t ]*\).*/\1/I p'
        fi
    else
        echo "Failed to connect to the keystone server on $DU_FQDN" >&2
        return 1
    fi
}
