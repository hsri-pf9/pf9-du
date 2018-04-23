#!/usr/bin/env bash

# Copyright (c) 2018 Platform9 Systems Inc.

COMMS_ENV_FILE=${COMMS_ENV_FILE:-"/etc/pf9/pf9-comms.env"}
SIDEKICK_ENV_FILE=${SIDEKICK_ENV_FILE:-"/etc/pf9/pf9-sidekick.env"}

function configure_comms() {
    local url="https://${DU_FQDN}/clarity/deployment_environment.txt"
    local deployment_env
    if deployment_env=$(curl -fs ${url}) ; then
        echo "deployment environment is ${deployment_env}"
        if [ "${deployment_env}" == "decco" ]; then
            set_sni_mode_to_fqdn
        fi
    else
        echo "deployment environment not available"
    fi
}

function set_sni_mode_to_fqdn() {
   echo SNI_USE_FQDN=1 >> ${COMMS_ENV_FILE}
   echo SNI_USE_FQDN=1 >> ${SIDEKICK_ENV_FILE}
}

