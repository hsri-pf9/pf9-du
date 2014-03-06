# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
in-memory certificate database for testing
"""

_db = {}

def set_ca(customer_id, key, cert):
    _db[customer_id] = {
        'ca': (key, cert),
        'services': {}
    }

def get_ca(customer_id):
    if customer_id not in _db:
        raise LookupError()
    return _db[customer_id]['ca']

def remove_ca(customer_id):
    if customer_id in _db:
        del _db[customer_id]

def set_cert(customer_id, service, key, cert):
    if customer_id not in _db:
        raise LookupError()
    _db[customer_id]['services'][service] = (key, cert)

def get_cert(customer_id, service):
    if customer_id not in _db or service not in _db[customer_id]['services']:
        raise LookupError()
    return _db[customer_id]['services'][service]

def remove_cert(customer_id, service):
    if customer_id not in _db or service not in _db[customer_id]['services']:
        raise LookupError()
    del _db[customer_id]['services'][service]
