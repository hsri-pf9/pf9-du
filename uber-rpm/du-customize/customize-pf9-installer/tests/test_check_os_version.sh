#!/bin/bash

source $(dirname $0)/../check_os_distro.sh


centos_ok=`ls $(dirname $0)/release-files/centos*.ok`
centos_ok_array=(${centos_ok// /})

centos_fail=`ls $(dirname $0)/release-files/centos*.fail`
centos_fail_array=(${centos_fail// /})

rhel_ok=`ls $(dirname $0)/release-files/rhel*.ok`
rhel_ok_array=(${rhel_ok// /})

rhel_fail=`ls $(dirname $0)/release-files/rhel*.fail`
rhel_fail_array=(${rhel_fail// /})

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
    local os=$3
    local expected_return_code=$4

    _check_version "${release_file}" ${distro} "${os}"
    if [[ $? != "${expected_return_code}" ]]; then
        format_print "${release_file}" ${distro} "FAILED"
        exit 1
    else
        format_print "${release_file}" ${distro} "OK"
    fi
}



for file in ${centos_ok_array[@]}
do
    test "${file}" REDHAT_VERSIONS centos "0"
done

for file in ${centos_fail_array[@]}
do
    test "${file}" REDHAT_VERSIONS centos "1"
done

for file in ${rhel_ok_array[@]}
do
    test "${file}" REDHAT_VERSIONS "red hat" "0"
done

for file in ${rhel_fail_array[@]}
do
    test "${file}" REDHAT_VERSIONS "red hat" "1"
done

for file in ${ubuntu_ok_array[@]}
do
    test "${file}" UBUNTU_VERSIONS ubuntu "0"
done

for file in ${ubuntu_fail_array[@]}
do
    test "${file}" UBUNTU_VERSIONS ubuntu "1"
done
