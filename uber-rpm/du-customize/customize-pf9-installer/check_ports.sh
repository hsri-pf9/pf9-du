#!/bin/bash
# Copyright (c) 2016 Platform9 Systems Inc.

# list of ports taken from pf9-comms's sni_maps/default.json
IMPORTANT_PORTS=(8158 5672 5673 3306 8023 9080 6264 5395 8558)
NET_TOOLS=(netstat ss)

function check_ports()
{
    local at_least_one_net_tool_exists="false"
    echo "Checking ports"
    for tool in "${NET_TOOLS[@]}"
    do
        if which $tool; then
            if [[ "${at_least_one_net_tool_exists}" == "true" ]]; then
                return
            fi
            at_least_one_net_tool_exists="true"
            for port in "${IMPORTANT_PORTS[@]}"
            do
                echo "Checking port $port"
                $tool -lptn | grep ":$port "
                if [[ $? == "0" ]]; then
                    in_use $port
                fi
            done
        fi
    done

    if [[ $at_least_one_net_tool_exists == "false" ]]; then
        echo
        echo "Cannot verify which ports are currently in use."
        echo "Please install 'netstat' or 'ss' and try running the installer again."

       if [[ "${TTY_AVAILABLE}" == "true" ]]; then
            read -p "Do you still want to continue? (yes/no) " yn
            case $yn in
                [Yy]* ) return 0;;
                [Nn]* ) exit 0;;
                *) echo "Please answer yes or no."; exit 1;;
            esac
       else
            echo "Continuing with installation..."
       fi
    fi
}

function in_use()
{
    local used_port=$1
    echo
    echo "Port $used_port is currently in use"
    echo
    echo "The Platform9 hostagent needs port $used_port to work properly."
    echo "Exiting..."
    return  ${IMPORTANT_PORT_OCCUPIED}
}
