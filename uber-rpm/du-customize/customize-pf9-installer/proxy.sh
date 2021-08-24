#!/bin/bash
# Copyright (c) 2015 Platform9 Systems Inc.

function proxy_ask()
{
    read -p "Do you want to configure proxy settings (yes/no)? " yn
    case $yn in
        [Yy]* ) SETUP_PROXY="true"; _ask_proxy_settings; return 0;;
        [Nn]* ) SETUP_PROXY="false"; return 0;;
        *) echo "Please answer yes or no."; exit 1;;
    esac
}

function proxy_setup()
{
    if [[ -z "${PROXY_HOST}" || -z "${PROXY_PORT}" ]]; then
      echo "Skipping proxy setup since the proxy host or the proxy port is not set."
      return
    fi

    echo "Setting up proxy with: "
    echo "protocol: $PROXY_PROTOCOL"
    echo "host: $PROXY_HOST"
    echo "port: $PROXY_PORT"

    if [[ -n "$PROXY_USER" ]] && [[ -n "$PROXY_PASS" ]]; then
        hostagent_proxy="http_proxy=\"${PROXY_PROTOCOL}://${PROXY_USER}:${PROXY_PASS}@${PROXY_HOST}:${PROXY_PORT}\""
        HOSTAGENT_PROXY="HTTP_PROXY=\"${PROXY_PROTOCOL}://${PROXY_USER}:${PROXY_PASS}@${PROXY_HOST}:${PROXY_PORT}\""
        hostagent_proxy_s="https_proxy=\"${PROXY_PROTOCOL}://${PROXY_USER}:${PROXY_PASS}@${PROXY_HOST}:${PROXY_PORT}\""
        HOSTAGENT_PROXY_S="HTTPS_PROXY=\"${PROXY_PROTOCOL}://${PROXY_USER}:${PROXY_PASS}@${PROXY_HOST}:${PROXY_PORT}\""
    else
        hostagent_proxy="http_proxy=\"${PROXY_PROTOCOL}://${PROXY_HOST}:${PROXY_PORT}\""
        HOSTAGENT_PROXY="HTTP_PROXY=\"${PROXY_PROTOCOL}://${PROXY_HOST}:${PROXY_PORT}\""
        hostagent_proxy_s="https_proxy=\"${PROXY_PROTOCOL}://${PROXY_HOST}:${PROXY_PORT}\""
        HOSTAGENT_PROXY_S="HTTPS_PROXY=\"${PROXY_PROTOCOL}://${PROXY_HOST}:${PROXY_PORT}\""
    fi

    if [[ ! -z ${NO_PROXY} ]]; then
        hostagent_noproxy="no_proxy=\"localhost,127.0.0.1,::1,localhost.localdomain,localhost4,localhost6,${NO_PROXY}\""
        HOSTAGENT_NOPROXY="NO_PROXY=\"localhost,127.0.0.1,::1,localhost.localdomain,localhost4,localhost6,${NO_PROXY}\""
    elif [[ ! -z ${no_proxy} ]]; then
        hostagent_noproxy="no_proxy=\"localhost,127.0.0.1,::1,localhost.localdomain,localhost4,localhost6,${no_proxy}\""
        HOSTAGENT_NOPROXY="NO_PROXY=\"localhost,127.0.0.1,::1,localhost.localdomain,localhost4,localhost6,${no_proxy}\""
    else
        hostagent_noproxy="no_proxy=\"localhost,127.0.0.1,::1,localhost.localdomain,localhost4,localhost6\""
        HOSTAGENT_NOPROXY="NO_PROXY=\"localhost,127.0.0.1,::1,localhost.localdomain,localhost4,localhost6\""
    fi

    if [[ -f "${PF9_HOSTAGENT_ENV_FILE}" ]]; then
        echo "${hostagent_proxy}" >> ${PF9_HOSTAGENT_ENV_FILE}
        echo "${HOSTAGENT_PROXY}" >> ${PF9_HOSTAGENT_ENV_FILE}
        echo "${hostagent_proxy_s}" >> ${PF9_HOSTAGENT_ENV_FILE}
        echo "${HOSTAGENT_PROXY_S}" >> ${PF9_HOSTAGENT_ENV_FILE}
        echo "${hostagent_noproxy}" >> ${PF9_HOSTAGENT_ENV_FILE}
        echo "${HOSTAGENT_NOPROXY}" >> ${PF9_HOSTAGENT_ENV_FILE}
    else
        echo "Hostagent env file: ${PF9_HOSTAGENT_ENV_FILE} not present."
        echo "Unable to write proxy settings in hostagent env file."
    fi

    json="{\"http_proxy\":{\"protocol\":\"${PROXY_PROTOCOL}\", \"host\":\"${PROXY_HOST}\", \"port\":${PROXY_PORT}"
    if [[ -n "$PROXY_USER" ]] && [[ -n "$PROXY_PASS" ]]; then
        json+=", \"user\":\"${PROXY_USER}\", \"pass\":\"${PROXY_PASS}\"}}"
    else
        json+="}}"
    fi

    echo "${json}" > ${PF9_COMMS_PROXY_CONF}
    chown pf9:pf9group ${PF9_COMMS_PROXY_CONF}
}

function _ask_proxy_settings()
{
    echo
    echo "Examples: "
    echo "http://squid.mycompany.com:3128"
    echo "https://username:password@squid.mycompany.com:443"
    echo

    while true; do
        read -p "proxy url: " PROXY_FULL_URL

        if [[ -z "${PROXY_FULL_URL}" ]]; then
            echo "Skipping proxy setup since the proxy url is not set."
            SETUP_PROXY="false"
        else
            PROXY_URL=($(./nettool urlparse "${PROXY_FULL_URL}"))

            if [[ $? != 0 ]]; then
                echo
                echo "Invalid proxy url. Please retry."
                continue
            fi
            parse_proxy_url
        fi



        read -p "Are these correct? (yes/no) " yn
        case $yn in
            [Yy]* ) break;;
            [Nn]* ) continue;;
            *) echo "Please answer yes or no.";;
        esac
    done
}

function parse_proxy_url() {
    echo "These are your proxy settings:"
    PROXY_PROTOCOL="${PROXY_URL[0]}"
    echo "protocol: \"$PROXY_PROTOCOL\""
    if [[ "${#PROXY_URL[@]}" = 3 ]]; then
        PROXY_HOST="${PROXY_URL[1]}"
        PROXY_PORT="${PROXY_URL[2]}"
        echo "host: \"$PROXY_HOST\""
        echo "port: \"$PROXY_PORT\""
    elif [[ "${#PROXY_URL[@]}" = 5 ]]; then
        PROXY_HOST="${PROXY_URL[1]}"
        PROXY_PORT="${PROXY_URL[2]}"
        PROXY_USER="${PROXY_URL[3]}"
        PROXY_PASS="${PROXY_URL[4]}"
        echo "host: \"$PROXY_HOST\""
        echo "port: \"$PROXY_PORT\""
        echo "user: \"$PROXY_USER\""
        echo "password: \"$PROXY_PASS\""
    else
        # If nettool succeeded, this shouldn't be reached
        echo "Unexpected result from proxy url parser: ${PROXY_URL[*]}"
        exit 1
    fi
}
