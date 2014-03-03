# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights Reserved.

import getpass
import re
import uuid
import requests
import time

def generate_amqp_vhost():
    """
    Returns a unique vhost string based on the current user and machine.
    :rtype: str
    """
    # Get the current user name.
    user = getpass.getuser()
    # This returns the mac of only one interface (presumably the first
    # interface). Should serve our need about mac.
    mac = ''.join(re.findall('..', '%012x' % uuid.getnode()))
    return "%s%s" % (user, mac)

def _get_amqp_broker_session(config):
    user = config.get('amqp', 'username')
    pwd = config.get('amqp', 'password')
    session = requests.Session()
    session.auth = (user, pwd)
    session.headers['content-type'] = 'application/json'
    return session

def prep_amqp_broker(config, log, amqp_endpoint):
    """
    Creates a vhost on an amqp broker in preparation
    for communications.
    :param config: a ConfigParser-like object with an 'amqp' section containing
     'username', 'password', and 'virtual_host' settings.
    :param log: a logger-like object
    :param amqp_endpoint: The broker url
    """
    session = _get_amqp_broker_session(config)
    vhost = config.get('amqp', 'virtual_host')
    url = "%s/vhosts/%s" % (amqp_endpoint, vhost)
    resp = session.get(url)
    log.info("Query vhost (%s) result: code=%d, body=%s", url, resp.status_code, resp.text)
    if resp.status_code != 404:
        # If the vhost endpoint existed previously, log it.
        # TODO: May be we should assert here in case the user is having
        # multiple instances of the test running
        log.warn("Cleaning up an existing version of the vhost at endpoint %s", url)
        clean_amqp_broker(config, log, amqp_endpoint)

    resp = session.put(url)
    log.info("Put vhost (%s) result: code=%d, body=%s", url, resp.status_code, resp.text)
    if resp.status_code not in range(200,300):
        raise Exception("AMQP broker virtual host setup failed.")

    # In addition to creating a virtual host setup, need to set perms for the
    # user on that virtual host
    perm = '{"configure":".*","write":".*","read":".*"}'
    url = "%s/permissions/%s/%s" % (amqp_endpoint, vhost, config.get('amqp', 'username'))
    resp = session.put(url, data=perm)
    log.info("Perm for vhost (%s) result: code=%d, body=%s", url, resp.status_code, resp.text)
    if resp.status_code not in range(200,300):
        raise Exception("AMQP broker virtual host permission setup failed.")


def clean_amqp_broker(config, log, amqp_endpoint):
    """
    Cleans up the work done by prep_amqp_broker(). The arguments are the same.
    """
    session = _get_amqp_broker_session(config)
    vhost = config.get('amqp', 'virtual_host')
    url = "%s/vhosts/%s" % (amqp_endpoint, vhost)
    attempts = 3
    for attempt in range(attempts):
        resp = session.delete(url)
        if resp.status_code in range(200, 300):
            return
        log.warn("Delete vhost (%s) result: code=%d, body=%s", url, resp.status_code, resp.text)
        time.sleep(1)
    raise Exception("Removal of virtual host in AMQP broker failed.")
