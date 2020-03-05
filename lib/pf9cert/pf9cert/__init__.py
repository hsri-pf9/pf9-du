# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights Reserved.

"""
This module contains the certificate module for maintaing certificates
These certificates are used for inter-service authentication for a given
customer. The following wiki has more details on the rationale for the
design and other higher level details:
https://platform9.atlassian.net/wiki/display/~rparikh/Certificate+Server
"""

# Root CA related operations

from os.path import dirname, realpath, join
from tempfile import mkdtemp
from shutil import copytree, rmtree
import subprocess
from . import persistence_mem as persist
_cur_dir = realpath(dirname(__file__))

class TempRootCADir(object):
    """
    Creates a temporary root CA directory from a template tree.
    Contains an openssl.cnf file suitable for CA and signing operations.
    Designed to be used with 'with' statement.
    """
    def __init__(self):
        pass

    def __enter__(self):
        srcTemplateDir = join(_cur_dir, 'root_ca_template')
        tmp_dir = mkdtemp(prefix='root_ca_')
        dst_dir = join(tmp_dir, 'root_ca')
        copytree(srcTemplateDir, dst_dir)
        self._tmpDir = tmp_dir
        return dst_dir

    def __exit__(self, exc_type, exc_val, exc_tb):
        rmtree(self._tmpDir)

def create_root_CA(customer_id, customer_fullname, days):
    """
    Creates a root certificate for a given customer (also generates key-pair)
    :param str customer_id: A unique short string identifying the customer
    :param str customer_fullname: A full display name like 'Platform9 Systems'
    :param int days: The expiration time expressed in days from now
    :return: (private_key, certificate) as strings in PEM format
    :rtype: tuple
    """
    with TempRootCADir() as root_dir:
        cmd = "openssl req -x509 -config openssl.cnf -newkey rsa:2048 "\
              "-days %d -out cacert.pem -outform PEM -subj /CN=%s/ -nodes" % \
              (days, customer_id)
        if subprocess.call(cmd.split(), cwd=root_dir) is not 0:
            raise Exception('Failed to create root CA')
        with open(join(root_dir, 'cacert.pem')) as file:
            cert = file.read()
        with open(join(root_dir, 'private/cakey.pem')) as file:
            private_key = file.read()
        persist.set_ca(customer_id, private_key, cert)
        return (private_key, cert)

def get_CA(customer_id):
    """
    Given a customer_id return the root certificate for the customer.
    :customer_id: The customer_id for which to fetch the root_certificate.
    :return: The certificate object
    """
    return persist.get_ca(customer_id)

def reissue_CA(customer_id, time_frame):
    """
    Reissue CA certificate for this customer_id
    :customer_id: the customer_id for which to reissue the root_Certificate
    :time_frame: New time frame for which to reissue the certificate
    :return: the private-key, certificate pair
    """
    raise NotImplementedError()

def revoke_CA(customer_id):
    """
    Revoke CA certificate for this customer_id
    :customer_id: the customer_id for which to revoke the root certificate
    :return: void if the operation succeeds else throws an exception (TODO)
    """
    raise NotImplementedError()

def remove_CA(customer_id):
    """
    Completely remove the CA Certificate from the system, this is generally done
    in scenario where we are cleaning up the remains of a given installation.
    :customer_id: the id of the customer for which to remove the root-ca
    :return: void
    """
    persist.remove_ca(customer_id)

# Operations related to a child certificate creation

def create_certificate(customer_id, service_id, days=365, for_server=False):
    """
    Creates a customer-specific, signed certificate for a pf9 service
    :param str customer_id: Id of customer whose root CA will be used for signing
    :param str service_id: common name of the service (like pf9-gateway, pf9-agent etc)
    :param int days: The expiration time expressed in days from now
    :param bool for_server: Whether this is for the server end of a connection. If true,
        keyUsage is set to keyEncipherment, else it is set to digitalSignature.
    :return: (private_key, certificate) as PEM-formatted strings
    :rtype: tuple
    """
    (ca_key, ca_cert) = get_CA(customer_id)
    with TempRootCADir() as root_dir:
        with open(join(root_dir, 'private', 'cakey.pem'), 'w') as file:
            file.write(ca_key)
        with open(join(root_dir, 'cacert.pem'), 'w') as file:
            file.write(ca_cert)
        svc_dir = join(root_dir, 'svc')

        ext_prefix = 'server' if for_server else 'client'
        for (cwd, cmd, desc) in [
            (svc_dir, 'openssl genrsa -out key.pem 2048', 'key'),
            (svc_dir, 'openssl req -new -key key.pem -out req.pem -outform PEM '\
              '-subj /CN=%s/O=services/ -nodes' % service_id, 'request'),
            (root_dir, 'openssl ca -config openssl.cnf -in svc/req.pem -out '\
              'svc/cert.pem -notext -batch -extensions %s_ca_extensions '\
              '-days %d' % (ext_prefix, days), 'certificate')]:
            if subprocess.call(cmd.split(), cwd=cwd) is not 0:
                raise Exception('Failed to generate %s for service %s for customer %s'
                                % (desc, service_id, customer_id))

        with open(join(svc_dir, 'cert.pem')) as file:
            cert = file.read()
        with open(join(svc_dir, 'key.pem')) as file:
            private_key = file.read()
        persist.set_cert(customer_id, service_id, private_key, cert)
        return (private_key, cert)

def get_certificate(customer_id, service_id):
    return persist.get_cert(customer_id, service_id)

def revoke_certificate(customer_id, service_id):
    """
    Revoke the certificate for the service_id (which is signed by customer_id)
    :customer_id:
    :service_id:
    """
    raise NotImplementedError()

def remove_certificate(customer_id, service_id):
    """
    Removes the certificate for the given customer_id, service_id pair
    :customer_id: id of the customer and hence the root CA which signed the
    certificate for the service_id
    :service_id: id of the service for which the certificate needs to be removed
    :return: None
    """
    persist.remove_cert(customer_id, service_id)

def reissue_certificate(customer_id, service_id, time_frame):
    """
    Reissue certificate for a given customer_id, service_id pair for the new
    time_frame
    :customer_id:
    :service_id:
    :return: private_key, certificate
    """
    raise NotImplementedError()
