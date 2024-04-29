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

from six import iteritems
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

    def get_all_ca(self):
        """
        Get all the CAs accepted by the DU
        """
        resp = self._session.get('%s/v1/cas' % self._vouch_addr)
        resp.raise_for_status()
        return resp.json()

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

        # The signing request through vouch leverages Vault to sign certs. Vault
        # follows the spec https://tools.ietf.org/html/rfc5280 which has an
        # upperbound of 64 chars for CN. Truncate the CN to the first 63 chars
        common_name = common_name[:62]
        LOG.info('Using the CN: %s', common_name)
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
            return 'v1' in resp_json
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
                                   common_name)]))
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
    for path, data in iteritems(cert_info):
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
                    LOG.info('Backing up directory %s to %s', path, backup)
                    os.rename(path, backup)
                    break
                else:
                    idx += 1

        with open(path, 'wb') as f:
            f.write(data)
        os.chown(path, pf9_uid, pf9group_gid)

    return backups

def place_new_CAs(ca_pem_file, ca_list):
    """
    Save adds the CA certs returned from vouch
    :param ca_list    : List of CAs returned from vouch
    :param ca_pem_file: CA file path
    """
    # TODO: Need some smarter logic to backup the
    # current CAs and restore on failed CA rotation
    pf9_uid = pwd.getpwnam('pf9')[2]
    pf9group_gid = grp.getgrnam('pf9group')[2]
    for certstr in ca_list:
        idx = 0
        while (True):
            ca = '%s.%d' % (ca_pem_file, idx)
            if os.path.isfile(ca):
                idx += 1
            else:
                with open(ca, 'wt') as f:
                    LOG.info('Writing CA cert to %s', ca)
                    f.write(certstr)
                    os.chown(ca, pf9_uid, pf9group_gid)
                break

def restart_service(svc_name):
    """
    Restart a service. Must be root or should have sudo rights.
    No check is done to see if a valid service name is passed.
    """
    LOG.info('Restarting {}...'.format(svc_name))
    try:
        subprocess.check_call(['sudo', 'systemctl', 'restart', svc_name])
        return True
    except subprocess.CalledProcessError:
        LOG.exception('systemctl failed, trying init-style service restart of {}...'.format(svc_name))

    try:
        subprocess.check_call(['sudo', 'service', svc_name, 'restart'])
        return True
    except subprocess.CalledProcessError:
        LOG.exception('service restart of {} failed, giving up'.format(svc_name))
    return False

def restart_comms_sidekick():
    """
    Restart the comms service followed by the sidekick service.
    Return False if either service runs into restart errors
    """
    svcs = ['pf9-comms', 'pf9-sidekick']
    hasErrors = False
    for s in svcs:
        if not restart_service(s):
            hasErrors = True

    return not hasErrors

def check_connection(vouch_url=COMMS_VOUCH_URL):
    wait_time = 0
    vouch = VouchCerts(vouch_url)
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
    for dest, src in iteritems(backups):
        os.unlink(dest)
        LOG.info("Restoring %s from backup %s", dest, src)
        os.rename(src, dest)
