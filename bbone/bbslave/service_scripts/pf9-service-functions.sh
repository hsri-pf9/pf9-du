# Copyright 2017 Platform9 Systems Inc.
# All Rights Reserved.

##
# This script provides some common service/daemon related functions across
# multiple OS systems. Consumers of the script don't have to worry about the
# underlying OS specific command to use.
##

# /etc/os-release is the source of truth for which OS and OS version is present
# on the host.
. /etc/os-release


is_ubuntu_14() {
    # Checks if the OS is Ubuntu14. If so, returns 0, else 1
    if [[ "$ID" == "ubuntu" && "$VERSION_ID" == "14.04" ]]
    then
        return 0
    else
        return 1
    fi
}

is_ubuntu_16() {
    # Checks if the OS is Ubuntu16. If so, returns 0, else 1
    if [[ "$ID" == "ubuntu" && "$VERSION_ID" == "16.04" ]]
    then
        return 0
    else
        return 1
    fi
}

is_ubuntu_18() {
   # Checks if the OS is Ubuntu18. If so, return 0, else 1
    if [[ "$ID" == "ubuntu" && "$VERSION_ID" == "18.04" ]]
    then
        return 0
    else
        return 1
    fi
}

is_ubuntu_20() {
   # Checks if the OS is Ubuntu20. If so, return 0, else 1
    if [[ "$ID" == "ubuntu" && "$VERSION_ID" == "20.04" ]]
    then
        return 0
    else
        return 1
    fi
}

is_centos_7() {
    # Checks if the OS is CentOS7. If so, returns 0, else 1
    if [[ "$ID" == "centos" && "$VERSION_ID" == "7" ]]
    then
        return 0
    else
        return 1
    fi
}

pf9_is_service_running() {
    # Check if a service is running. Service name is passed as an argument to
    # the function.
    if is_ubuntu_14
    then
        service $1 status
    else
        systemctl is-active $1
    fi

    return $?
}


pf9_service_restart() {
    # Restart a service. Service name is passed as an argument to the function.
    if is_ubuntu_14
    then
        service $1 restart
    else
        systemctl restart $1
    fi

    return $?
}


pf9_service_stop() {
    # Stop a service. Service name is passed as an argument to the function.
    if is_ubuntu_14
    then
        service $1 stop
    else
        systemctl stop $1
    fi

    return $?
}


pf9_service_start() {
    # Start a service. Service name is passed as an argument to the function.
    if is_ubuntu_14
    then
        service $1 start
    else
        systemctl start $1
    fi

    return $?
}

pf9_service_condrestart() {
    # Conditional restart a service. Service name is passed as an argument to the function.
    if is_ubuntu_14
    then
        service $1 condrestart
    else
        systemctl condrestart $1
    fi

    return $?
}

pf9_daemon_reload_if_needed() {
    # Invoke reload of systemd unit files.
    if ! is_ubuntu_14
    then
        systemctl daemon-reload
    fi

    return $?
}


pf9_setup_service_files() {
    # Sets up an init script or systemd unit depending on the OS flavor. systemd
    # reload is also performed if the host is systemd based host.
    # Arguments to the function
    # $1: Name of the service to install. Creates files with this name
    # $2: Source systemd unit file
    # $3: Source initd file
    if is_ubuntu_14
    then
        cp $3 /etc/init.d/$1
    else
        cp $2 /lib/systemd/system/"${1}.service" && pf9_daemon_reload_if_needed
    fi

    return $?
}

pf9_remove_service_files() {
    # Removes an init script or systemd unit depending on the OS flavor. systemd
    # reload is also performed if the host is systemd based host.
    # Arguments to the function
    # $1: Name of the service to remove. Expects the init script to be this name
    # or the systemd unit file to be {$1}.service
    if is_ubuntu_14
    then
        rm /etc/init.d/$1
    else
        # TODO: Should clean up other systemd dirs as well?
        rm /lib/systemd/system/"${1}.service" && pf9_daemon_reload_if_needed
    fi

    return $?
}

pf9_disable_service_on_boot() {
    # Remove the service from startup on boot. Service name is passed as an
    # argument to the function.
    if is_ubuntu_14
    then
        update-rc.d $1 remove
    else
        systemctl disable $1
    fi

    return $?
}

pf9_enable_service_on_boot() {
    # Add the service to startup on boot. Service name is passed as an
    # argument to the function.
    if is_ubuntu_14
    then
        update-rc.d $1 defaults
    else
        systemctl enable $1
    fi

    return $?
}
