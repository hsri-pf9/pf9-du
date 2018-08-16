#!/usr/bin/env bash

# Copyright (c) 2018 Platform9 Systems Inc.

COMMS_ENV_FILE=${COMMS_ENV_FILE:-"/etc/pf9/pf9-comms.env"}
SIDEKICK_ENV_FILE=${SIDEKICK_ENV_FILE:-"/etc/pf9/pf9-sidekick.env"}

function configure_comms() {
    local url="https://${DU_FQDN}/clarity/deployment_environment.txt"
    local deployment_env
    local err_log="/tmp/depl_env_curl_err.log"
    echo "$(date) - downloading ${url}"
    if deployment_env=$(curl -f ${url} 2> ${err_log} ) ; then
        echo "deployment environment is ${deployment_env}"
        if [ "${deployment_env}" == "decco" ]; then
            set_sni_mode_to_fqdn
        fi
    else
        echo "deployment environment not available"
        if [ -n "${DEPL_ENV_WEBHOOK}" ] ; then
            msg="host $(hostname) failed to download deployment environment file from DU ${DU_FQDN}"
            curl -d "{\"text\":\"$msg\"}" "${DEPL_ENV_WEBHOOK}"
            echo ${msg}
            # treat this is a fatal error
            exit 1
        fi
    fi
}

function set_sni_mode_to_fqdn() {
   echo SNI_USE_FQDN=1 >> ${COMMS_ENV_FILE}
   echo SNI_USE_FQDN=1 >> ${SIDEKICK_ENV_FILE}
}

