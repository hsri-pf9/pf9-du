#!/usr/bin/env python
# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved
#

__author__ = 'Platform9'

#
# Update keystone endpoints so that public services are visible to clients
# XXX: Must invoke after database is initialized and connected
#

import os
import subprocess
import sys
import logging
import re
from subprocess import Popen, PIPE

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M')
log = logging.getLogger('update-endpoints')

if __name__ == "__main__":
    if 'DU_FQDN' not in os.environ.keys():
        log.error('DU_FQDN is not set in env')
        sys.exit(1)

    # Get mysql string
    p = Popen(['openstack-config', '--get','/etc/keystone/keystone.conf', 'sql', 'connection'],
              stdout=PIPE, stderr=PIPE)

    p.wait()

    if p.returncode:
        error_msg = p.stderr.read()
        msg = 'Unable to read config, error: %d, %s'% (p.returncode, error_msg)
        raise SystemError(msg)

    sql_conn_str = p.stdout.readline()

    # mysql://<user>:<password>@<host>/<database>[;port]
    pattern = r'mysql://([^:]+):([^/]+)@([^:$]+)/(.+)(?::(\d+))?'
    matches = re.match(pattern, sql_conn_str)

    if not matches or len(matches.groups()) < 5:
        msg = 'connection string invalid: %s' % sql_conn_str
        log.error(msg)
        raise ValueError(msg)

    (user, passwd, host, db_name) = matches.groups()[:4]

    if len(matches.groups()) == 5 and matches.groups()[4]:
        port = int(matches.groups()[4])
        log.info("Initiating database customization for {0}@{1}:{2}".format(user, host, port))
    else:
        port = None
        log.info("Initiating database customization for {0}@{1}".format(user, host))

    fqdn = os.environ['DU_FQDN']
    default_url_prefix = 'http://127.0.0.1'
    new_url_prefix = 'https://%s' % fqdn
    endpoint_updates = [('5000/', 'keystone'),
                        ('35357/', 'keystone_admin'),
                        ('8774/', 'nova')]
                        ('9292', 'glance')]

    for endpoint in endpoint_updates:
        old_endpoint = '%s:%s' % (default_url_prefix, endpoint[0])
        new_endpoint = '%s/%s/' % (new_url_prefix, endpoint[1])
        update_query = 'update endpoint set url = REPLACE(url, \'%s\', \'%s\') where ' \
                       'interface in (\'public\', \'admin\')' % (old_endpoint, new_endpoint)
        log.debug('Executing: %s', update_query)
        update_cmd = ['mysql', '-h'+ host, '-u' + user, '-p' + passwd, '-e' + update_query, db_name]
        subprocess.check_call(update_cmd)
