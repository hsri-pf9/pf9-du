#!/bin/bash
# Copyright (c) 2015 Platform9 Systems Inc.


function support_generate_bundle()
{
    echo
    echo "Installation failed..."

    _collect_info
    tar -czf ${SUPPORT_BUNDLE} ${SUPPORT_DIRS[@]} ${SYSTEM_INFO_LOG} > /dev/null 2>&1

    mv ${SUPPORT_BUNDLE} /tmp
    echo
    echo "Please email us at support@platform9.com with a copy of the installation's output and /tmp/${SUPPORT_BUNDLE} as an attachment"
    echo
}

function _collect_info()
{
    date > ${SYSTEM_INFO_LOG}
    _run_support_commands support.common
    _run_support_commands support.${DISTRO}
}

# execute each line of the file ${file}
# all output are redirected to ${SYSTEM_INFO_LOG}
function _run_support_commands()
{
    local file=$1

    cat "${file}" | while read command
    do
        echo "" >> ${SYSTEM_INFO_LOG}
        echo "==========> "$command" <==========" >> ${SYSTEM_INFO_LOG}
        bash -c "$command" >> ${SYSTEM_INFO_LOG} 2>&1
    done
}
