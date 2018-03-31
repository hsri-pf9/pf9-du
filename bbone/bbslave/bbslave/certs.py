# Copyright (c) 2018 Platform9 Systems Inc. All Rights Reserved.

import errno
import json
import grp
import logging
import os
import pwd
import requests
import subprocess
import time

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import rsa
from cryptography.x509.oid import NameOID
from cryptography.hazmat.primitives.serialization import (Encoding,
                                                          PrivateFormat,
                                                          NoEncryption)
LOG = logging.getLogger(__name__)

COMMS_VOUCH_URL = 'http://localhost:8558'
COMMS_RESTART_TIMEOUT = 60
COMMS_RESTART_CHECK_INTERVAL = 2

class VouchCerts(object):
    def __init__(self, vouch_addr, keystone_token=None):
        self._vouch_addr = vouch_addr
        self._token = keystone_token
        self._session = requests.Session()
        if keystone_token:
            self._session.headers.update({'X-Auth-Token': keystone_token})

    def get_ca(self):
        """
        Get the configured CA certificate from vouch.
        """
        resp = self._session.get('%s/v1/sign/ca' % self._vouch_addr)
        resp.raise_for_status()
        return resp.json()['certificate']

    def sign_csr(self, csr, common_name):
        """
        Sign a csr
        :param csr: pem encoded CSR
        :param common_name: common name
        :returns: (new cert, issuing CA cert)
        """
        LOG.info('Sending CSR to vouch for signature, pem = %s', csr)
        body = {
            'common_name': common_name,
            'csr': csr
        }
        resp = self._session.post('%s/v1/sign/cert' % self._vouch_addr,
                                  data=json.dumps(body))
        resp.raise_for_status()
        cert_data = resp.json()
        return cert_data['certificate'], cert_data['issuing_ca']

    def supports_v1(self):
        """
        Try to get the version information from the vouch service. If it's
        there and lists a v1 url, return True, else False.
        """
        LOG.info('Checking for vouch at %s...', self._vouch_addr)
        try:
            resp = self._session.get(self._vouch_addr)
            resp.raise_for_status()
            resp_json = resp.json()
            LOG.info('Vouch version response: %s', resp_json)
            return resp_json.has_key('v1')
        except (requests.ConnectionError, requests.HTTPError) as e:
            LOG.info('Could not fetch version info from vouch, cannot sign '
                      'certs using %s: %s', self._vouch_addr, e)
            return False
        except ValueError as e:
            LOG.exception('Bad response from vouch address %s: %s',
                          self._vouch_addr, e)
            return False

def generate_key_and_csr(common_name):
    LOG.info('Generating new private key and CSR for %s.', common_name)
    private_key = rsa.generate_private_key(public_exponent=65537,
                                           key_size=2048,
                                           backend=default_backend())
    builder = x509.CertificateSigningRequestBuilder()
    builder = builder.subject_name(x509.Name([
                x509.NameAttribute(NameOID.COMMON_NAME,
                                   unicode(common_name))]))
    builder = builder.add_extension(
        x509.BasicConstraints(ca=False, path_length=None), critical=True)
    request = builder.sign(private_key, hashes.SHA256(), default_backend())
    return (
        private_key.private_bytes(Encoding.PEM, PrivateFormat.PKCS8,
                                  NoEncryption()),
        request.public_bytes(Encoding.PEM)
    )

def backup_and_save_certs(cert_info):
    """
    Save and backup the certs in cert_info. Parent directories are created.
    If there are existing files, backups are created and a map of backups
    is returned.
    :param cert_info: dictionary of filename->pem contents to save to
                      disk.
    :return: dictionary of backed up filenames original->backup
    """
    pf9_uid = pwd.getpwnam('pf9')[2]
    pf9group_gid = grp.getgrnam('pf9group')[2]
    backups = {}
    for path, data in cert_info.iteritems():
        try:
            parent = os.path.dirname(path)
            os.makedirs(parent)
            LOG.info('Created directory %s', parent)
        except OSError as e:
            if e.errno == errno.EEXIST:
                LOG.info('Directory %s exists', parent)
            else:
                raise

        # backup the old file if it exists
        if os.path.isfile(path):
            idx = 0
            while (True):
                backup = '%s.%d' % (path, idx)
                if not os.path.isfile(backup):
                    backups[path] = backup
                    os.rename(path, backup)
                    break
                else:
                    idx += 1

        with open(path, 'w') as f:
            f.write(data)
        os.chown(path, pf9_uid, pf9group_gid)

    return backups

def restart_comms():
    """
    Restart the comms service. Must be root.
    """
    LOG.info('Restarting pf9-comms...')
    try:
        subprocess.check_call(['systemctl', 'restart', 'pf9-comms'])
        return True
    except subprocess.CalledProcessError:
        LOG.exception('systemctl failed, trying init-style service restart...')

    try:
        subprocess.check_call(['service', 'pf9-comms', 'restart'])
        return True
    except subprocess.CalledProcessError:
        LOG.exception('service restart failed, giving up')
    return False

def check_connection():
    wait_time = 0
    vouch = VouchCerts(COMMS_VOUCH_URL)
    while wait_time <= COMMS_RESTART_TIMEOUT:
        LOG.info('Checking connection by attempting to talk to vouch through '
                 'comms, wait = %d...', wait_time)
        if vouch.supports_v1():
            LOG.info('Success')
            return True
        else:
            time.sleep(COMMS_RESTART_CHECK_INTERVAL)
            wait_time += COMMS_RESTART_CHECK_INTERVAL
    LOG.error('Failed to contact vouch service through comms in %s seconds',
              COMMS_RESTART_TIMEOUT)
    return False

def restore_backups(backups):
    for dest, src in backups.iteritems():
        os.unlink(dest)
        os.rename(src, dest)
