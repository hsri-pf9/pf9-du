#!/usr/bin/python

# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved

# Requires the following environment variables:
# ADMINUSER - user to create
# ADMINPASS - password
# ADMINEMAIL - email

from keystoneclient.v2_0 import client
from keystoneclient.apiclient.exceptions import Conflict
import logging
import os
import re
from novaclient.v1_1 import client as nv_client
from subprocess import call

keystone_endpoint = 'http://localhost:35357/v2.0'
default_tenant = 'service'
default_role = 'admin'

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M')
log = logging.getLogger('user-setup')

log.info("Starting deployment unit user setup")

# get params from environment
admin_user = os.getenv('ADMINUSER')
if not admin_user:
    log.error("ADMINUSER name not found in env")
    exit(1)

admin_pass = os.getenv('ADMINPASS')
if not admin_pass:
    log.error("ADMINPASS password not found in env")
    exit(1)

admin_email = os.getenv('ADMINEMAIL')
if not admin_email:
    log.error("ADMINEMAIL address not found in env")
    exit(1)

# get the admin token from the keystone config
with open('/etc/keystone/keystone.conf') as kscfg :
    for line in kscfg.readlines() :
        match = re.match(r'admin_token\s*=\s*(\w+)', line)
        if match:
            admin_token = match.group(1)
            break
if not admin_token:
    log.error("No admin token in keystone.conf")
    exit(1)

# keystone client
log.info('Connecting to keystone at %s' % keystone_endpoint)
ks = client.Client(token=admin_token, endpoint=keystone_endpoint)

# admin role
try :
    admin_role = ks.roles.create(default_role)
    log.info("Created role %s" % default_role)
except Conflict:
    roles = ks.roles.list()
    admin_role = [r for r in roles if r.name == default_role][0]
    log.info('Found role %s' % default_role)
except Exception as ex:
    log.error('Failed to get/create role: %s' % ex)
    exit(1)

# create the tenant
try :
    service_tenant = ks.tenants.create(tenant_name=default_tenant,
                                       description='platform9 customer tenant',
                                       enabled=True)
    log.info("Created tenant %s" % default_tenant)
except Conflict :
    tenants = ks.tenants.list()
    service_tenant = [t for t in tenants if t.name == default_tenant][0]
    log.info('Found role %s' % default_role)
except Exception as ex:
    log.error('Failed to get/create tenant: %s' % ex)
    exit(1)


# create the user and make him an admin, conflict is an error
try :
    user = ks.users.create(name=admin_user,
                           password=admin_pass,
                           tenant_id=service_tenant.id,
                           email=admin_email)
    ks.roles.add_user_role(user, admin_role, service_tenant)
    log.info("Created user %s" % admin_user)
except Exception as ex:
    log.error('Failed to create user %s : %s' % (admin_user, ex))
    exit(1)

log.info('Adding information on Platform9 users and projects')

try:
    nc = nv_client.Client(admin_user, admin_pass, default_tenant,
                          auth_url=keystone_endpoint, http_log_debug=True)
    log.info('Completed nova client initialization.')
    nova_status_code = call(["service", "openstack-nova-api", "status"])
    log.info("openstack-nova-api status code: %s" % nova_status_code)
    nc.quotas.update(service_tenant.id, instances=-1, ram=-1, cores=-1, floating_ips=-1)
    nova_status_code = call(["service", "openstack-nova-api", "status"])
    log.info("openstack-nova-api status code: %s" % nova_status_code)
    log.info('Completed nova quota update.')
except Exception as ex:
    log.error("Failed to update quota: %s" % ex)
    exit(1)

# Set quota, add user and tenant info to nova.conf
lines = ["[PF9]", ''.join(["pf9_project_id", "=", service_tenant.id]),
         ''.join(["pf9_user_id", "=", user.id])]

with open('/etc/nova/nova.conf', 'a') as novaCfg:
    for line in lines:
        novaCfg.write(line + '\n')

log.info('Successfully added Platform9 user and system information to nova config')

# Add tenant id information to janitor.conf
with open('/etc/pf9/janitor.conf', 'a') as f:
    for line in lines:
        f.write(line + '\n')

log.info('Successfully added Platform9 user and system information to janitor config')
