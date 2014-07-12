#!/usr/bin/env bash

# Create the pf9 user and group
id pf9 &>/dev/null || useradd pf9
grep ^pf9group: /etc/group &>/dev/null || groupadd pf9group
usermod -aG pf9group pf9
# Add root also to the pf9group
usermod -aG pf9group root

# Make the certs file belong to the pf9group
chgrp -R pf9group /etc/pf9/certs/*
service pf9-hostagent start
