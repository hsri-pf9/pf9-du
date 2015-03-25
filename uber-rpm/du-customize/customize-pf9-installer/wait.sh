#!/bin/bash
# Copyright (c) 2015 Platform9 Systems Inc.

wait_dir_exists()
{
    local seconds=$1
    local dir=$2
    local tries=0
    local max_tries=$((seconds * 2))

    until [[ -d $dir ]]; do
        printf "."
        tries=$((tries + 1))
        [[ $tries -eq $max_tries ]] && { echo; echo "Timeout waiting for existence of $dir"; return 1; }
        sleep .5
    done
}

wait_file_exists()
{
    local seconds=$1
    local file=$2
    local tries=0
    local max_tries=$((seconds * 2))

    until [[ -e $file ]]; do
        printf "."
        tries=$((tries + 1))
        [[ $tries -eq $max_tries ]] && { echo; echo "Timeout waiting for existence of $file"; return 1; }
        sleep .5
    done
}

wait_service_running()
{
    local seconds=$1
    local service=$2
    local retval=1
    local tries=0
    local max_tries=$((seconds * 2))

    until [[ $retval == "0" ]]; do
        service ${service} status
        retval=$?
        tries=$((tries + 1))
        [[ $tries -eq $max_tries ]] && { echo; echo "Timeout waiting for ${service} to start"; return 1; }
        sleep .5
    done
}

