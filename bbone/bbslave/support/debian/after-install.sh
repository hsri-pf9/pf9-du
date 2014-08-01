#!/usr/bin/env bash

# Create the pf9 user and group
grep ^pf9group: /etc/group &>/dev/null || groupadd pf9group
id pf9 &>/dev/null || useradd -g pf9group -d / -s /usr/sbin/nologin -c "Platform9 user" pf9
# In cases where pf9 user exists but is not part of the pf9group, explicitly
# add them
usermod -aG pf9group pf9
# Add root also to the pf9group
usermod -aG pf9group root

# Make the certs file belong to the pf9group
chgrp -R pf9group /etc/pf9/certs/*
service pf9-hostagent start
