#!/bin/bash

source $(dirname $0)/../check_os_distro.sh


redhat_ok=`ls $(dirname $0)/release-files/redhat-*.ok`
redhat_ok_array=(${redhat_ok// /})

redhat_fail=`ls $(dirname $0)/release-files/redhat-*.fail`
redhat_fail_array=(${redhat_fail// /})

ubuntu_ok=`ls $(dirname $0)/release-files/ubuntu-*.ok`
ubuntu_ok_array=(${ubuntu_ok// /})

ubuntu_fail=`ls $(dirname $0)/release-files/ubuntu-*.fail`
ubuntu_fail_array=(${ubuntu_fail// /})


function format_print()
{
    local release_file=$1
    local distro=$2
    local status=$3

    local padlength=60
    local pad=$(printf '%0.1s' "-"{1..60})

    printf '%s' "${release_file} "
    printf '%*.*s' 0 $((padlength - ${#release_file})) "${pad}"
    printf '%s' "${status}"
    printf '%s\n' " ${!distro// / }"
}


function test()
{
    local release_file=$1
    local distro=$2[@]
    local expected_return_code=$3

    _check_version "${release_file}" ${distro}
    if [[ $? != "${expected_return_code}" ]]; then
        format_print "${release_file}" ${distro} "FAILED"
        exit 1
    else
        format_print "${release_file}" ${distro} "OK"
    fi
}



for file in ${redhat_ok_array[@]}
do
    test "${file}" REDHAT_VERSIONS "0"
done

for file in ${redhat_fail_array[@]}
do
    test "${file}" REDHAT_VERSIONS "1"
done

for file in ${ubuntu_ok_array[@]}
do
    test "${file}" UBUNTU_VERSIONS "0"
done

for file in ${ubuntu_fail_array[@]}
do
    test "${file}" UBUNTU_VERSIONS "1"
done
