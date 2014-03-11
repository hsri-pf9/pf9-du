# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
Given a unique customer short name, generates a root CA certificate for
the customer, and uses it to sign 3 certificates for rabbit broker,
backbone master, and backbone slave.

Usage: python gen_certs.py <CUSTOMER_SHORT_NAME> <CUSTOMER_FULLNAME> <EXPIRATION_DAYS>
"""

from pf9cert import create_root_CA, create_certificate
from os.path import join, exists
from os import makedirs
import sys

debug = True

if len(sys.argv) != 5:
    print 'Usage: python gen_certs.py <BASEDIR> <CUSTOMER_SHORT_NAME> <CUSTOMER_FULL_NAME> <EXPIRATION_DAYS>'
    print 'Example: python gen_certs.py /etc/pf9/certs foobar "Foo Bar, Inc." 100'
    sys.exit(1)

def write_key_and_cert(base_dir, svcname, key, cert):
    data = [('key.pem', key), ('cert.pem', cert)]
    for (name, buf) in data:
        dir = join(base_dir, svcname)
        if not exists(dir):
            makedirs(dir)
        fpath = join(dir, name)
        with open(fpath, 'w') as file:
            file.write(buf)
        print 'Wrote %s' % fpath

services = [('broker', True), ('bbmaster', False), ('hostagent', False)]

base_dir = sys.argv[1]
cust_name = sys.argv[2]
cust_fullname = sys.argv[3]
days = int(sys.argv[4])
(key, cert) = create_root_CA(cust_name, cust_fullname, days)
write_key_and_cert(base_dir, 'ca', key, cert)
for (svcname, for_server) in services:
    (key, cert) = create_certificate(customer_id=cust_name,
                                     service_id=svcname,
                                     days=days,
                                     for_server=for_server)
    write_key_and_cert(base_dir, svcname, key, cert)

