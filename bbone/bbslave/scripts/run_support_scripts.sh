#!/bin/bash

usage() {
    echo "Usage: $0 <support_logging_dir>"
    exit 1
}

[ "$#" != "1" ] && usage

support_logging_dir=$1
support_script_dir=/opt/pf9/support

# Exit if the directory to write to is invalid.
mkdir -p "$support_logging_dir"
if [ "$?" != "0" ]; then
    echo "Invalid support logging directory: $support_logging_dir" 1>&2
    exit 1
fi

# Exit if the support script directory does not exist
if [ ! -d "$support_script_dir" ]; then
    echo "Support script directory does not exist: $support_script_dir" 1>&2
fi

cd "$support_script_dir"

exit_code=0
for script in *; do
    # Skip directories and non-executable files
    test -d $script && continue
    ! test -x $script && continue
    echo "[Running $script]"
    script_outfile="${support_logging_dir}/${script%.sh}.txt"
    timeout -s KILL 3m ./$script > $script_outfile 2>&1
    RETVAL=$?
    case $RETVAL in
        0)
            continue
            ;;
        137)
            echo "ERROR: Timeout after 3 minutes. Killed with SIGKILL."
            exit_code=1
            ;;
        *)
            echo "ERROR: Failed with exit status $RETVAL."
            exit_code=1
            ;;
    esac
done

exit $exit_code
