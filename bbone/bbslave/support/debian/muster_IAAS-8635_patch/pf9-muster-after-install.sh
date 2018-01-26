#!/bin/sh

# used only by the DEB installer

mkdir -p /var/run/pf9-muster
mkdir -p /etc/pf9/pf9-muster/jobs
mkdir -p /opt/pf9/pf9-muster/jobs
mkdir -p /var/cache/pf9-muster/jobs

chown -R pf9:pf9group /var/run/pf9-muster
chown -R pf9:pf9group /var/log/pf9/*
chown -R pf9:pf9group /etc/pf9/pf9-muster
chown -R pf9:pf9group /opt/pf9/pf9-muster
chown -R pf9:pf9group /var/cache/pf9-muster

chown root:root /etc/sudoers.d/pf9-muster

# Remove exited containers created by pf9-muster (PMK-1044)
remove_muster_containers()
{
    # Only remove containers if the script can run `docker ps`
    if docker ps > /dev/null; then
        # Ignore all errors
        set +e
        echo "Cleaning up exited containers created by pf9-muster"
        docker ps --all --filter "status=exited" --format "{{.ID}} {{.Command}}" --no-trunc \
        | grep "/bin/sh -c 'echo beetlejuice beetlejuice beetlejuice'" \
        | cut -f1 -d" " \
        | xargs -n1 docker rm
    fi
    return 0
}

remove_muster_containers
