#!/usr/bin/python

# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved

# Requires the following environment variables:
# ADMINUSER - user to create
# ADMINPASS - password
# ADMINEMAIL - email

from keystoneclient.v3 import client
from keystoneclient.apiclient.exceptions import Conflict
from keystoneclient.exceptions import ConnectionError

import logging
import os
import re
import time
import uuid
from novaclient.v1_1 import client as nv_client
from subprocess import call, check_call

keystone_endpoint = 'http://localhost:5000/v3'
default_tenant = 'service'
default_role = 'admin'
self_service_role = '_member_'
global_conf = '/etc/pf9/global.conf'

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
ks = client.Client(token=admin_token, endpoint=keystone_endpoint, insecure=True)

# make sure the keystone API is ready:
max_wait = 300
interval = 5
wait = 0

while True :
    try :
        users = ks.users.list()
        log.info("The number of existing keystone users is %d" % len(users))
        break
    except ConnectionError :
        if wait > max_wait :
            log.error("Timed out waiting for a response from keystone!")
            exit(1)
        else :
            log.info("Waiting for keystone %s seconds..." % wait)
            wait += interval
            time.sleep(interval)
    except Exception as ex :
        log.error("Failed to make contact with keystone: %s" % ex)
        exit(1)

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
    member_role = [r for r in roles if r.name == self_service_role][0]
    ks.roles.add_user_role(user, admin_role, service_tenant)
    ks.roles.remove_user_role(user, member_role, service_tenant)
    log.info("Created user %s" % admin_user)
except Exception as ex:
    log.error('Failed to create user %s : %s' % (admin_user, ex))
    exit(1)

# create an imagelib user that allows the image library to validate user
# auth tokens with keystone. Save the name, password and tenant in global.conf
# so that resmgr can use it to configure the imagelibrary at role assign-time.
# Make him part of the services tenant (not the service tenant).
try:
    # get the services tenant
    tenants = ks.tenants.list()
    services_tenant = None
    for t in tenants:
        if t.name == 'services':
            services_tenant = t
            break
    if not services_tenant:
        log.error('Could not find services tenant!')
        exit(1)

    # add the user
    imglib_username = 'imagelib'
    imglib_password = uuid.uuid1().hex
    imglib_user = ks.users.create(name=imglib_username,
                                  password=imglib_password,
                                  tenant_id=services_tenant.id,
                                  email='imagelib@localhost')
    ks.roles.add_user_role(imglib_user, admin_role, services_tenant)
    log.info("Created user %s" % imglib_user)

    # now add the username, password and tenant name to global.conf
    check_call(['openstack-config', '--set', global_conf, 'pf9-imagelibrary',
                'auth_user', imglib_username])
    check_call(['openstack-config', '--set', global_conf, 'pf9-imagelibrary',
                'auth_pass', imglib_password])
    check_call(['openstack-config', '--set', global_conf, 'pf9-imagelibrary',
                'auth_tenant_name', 'services'])

except Conflict:
    # The user already exists. make sure that global.conf has values
    res1 = call(['openstack-config', '--get', global_conf, 'pf9-imagelibrary',
                 'auth_user'])
    res2 = call(['openstack-config', '--get', global_conf, 'pf9-imagelibrary',
                 'auth_pass'])
    res3 = call(['openstack-config', '--get', global_conf, 'pf9-imagelibrary',
                 'auth_tenant_name'])
    if not all([res1 == 0, res2 == 0, res3 == 0]):
        log.error("Found existing imagelib user, but global.conf doesn't "
                "have username/password/service configuration")
        exit(1)
    else:
        log.info("user 'imagelib' already exists, global.conf has values")

except Exception as ex:
    log.error("Failed to create imagelib user: %s" % ex)
    exit(1)

log.info('Adding information on Platform9 users and projects')

try:
    nc = nv_client.Client(admin_user, admin_pass, default_tenant,
                          auth_url=keystone_endpoint, insecure=True, http_log_debug=True)
    log.info('Completed nova client initialization.')
    nova_status_code = call(["service", "openstack-nova-api", "status"])
    log.info("openstack-nova-api status code: %s" % nova_status_code)
    nc.quotas.update(service_tenant.id, instances=-1, ram=-1, cores=-1, floating_ips=-1)
    nova_status_code = call(["service", "openstack-nova-api", "status"])
    log.info("openstack-nova-api status code: %s" % nova_status_code)
    log.info('Completed nova quota update.')
    nc.flavors.create('pf9.unknown', 1, 1, 0, flavorid=94086)
    nova_status_code = call(["service", "openstack-nova-api", "status"])
    log.info("openstack-nova-api status code: %s" % nova_status_code)
    log.info('Completed flavor creation')
except Exception as ex:
    log.error("Failed to update quota or create flavor: %s" % ex)
    exit(1)

try:
    # Set quota, add user and tenant info to nova.conf
    check_call(['openstack-config', '--set', '/etc/nova/nova.conf',
                'PF9', 'pf9_project_id', service_tenant.id])
    check_call(['openstack-config', '--set', '/etc/nova/nova.conf',
                'PF9', 'pf9_user_id', user.id])
    check_call(['openstack-config', '--set', '/etc/nova/nova.conf',
                'PF9', 'pf9_flavor', 'pf9.unknown'])
    log.info('Successfully added Platform9 user, system and flavor information to nova config')
    # Add tenant id information to janitor.conf
    check_call(['openstack-config', '--set', '/etc/pf9/janitor.conf',
                'PF9', 'pf9_project_id', service_tenant.id])
    check_call(['openstack-config', '--set', '/etc/pf9/janitor.conf',
                'PF9', 'pf9_user_id', user.id])
    log.info('Successfully added Platform9 user and system information to janitor config')
except:
    log.exception('Failed to update user and tenant info')
    exit(1)

