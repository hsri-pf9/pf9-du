#!/bin/bash
# Copyright (c) 2015 Platform9 Systems Inc.


function support_generate_bundle()
{
    echo
    echo "Installation may have failed..."

    _collect_info
    tar -czf ${SUPPORT_BUNDLE} ${SUPPORT_DIRS[@]} ${SUPPORT_FILE} > /dev/null 2>&1

    mv ${SUPPORT_BUNDLE} /tmp
    echo
    echo "Please email support@platform9.com with /tmp/${SUPPORT_BUNDLE} as an attachment"
    echo
}

function _collect_info()
{
    date > ${SUPPORT_FILE}
    _run_support_commands support.common
    _run_support_commands support.${DISTRO}
}

# execute each line of the file ${file}
# all output are redirected to ${SUPPORT_FILE}
function _run_support_commands()
{
    local file=$1

    cat "${file}" | while read command
    do
        echo "" >> ${SUPPORT_FILE}
        echo "==========> "$command" <==========" >> ${SUPPORT_FILE}
        bash -c "$command" >> ${SUPPORT_FILE} 2>&1
    done
}
