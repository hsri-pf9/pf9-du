# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights Reserved.

from unittest import TestCase

import pf9cert
from OpenSSL import crypto
from datetime import datetime as dt
import struct

KEY_USAGE_CERT_SIGN = 0x6010203
KEY_USAGE_DIGITAL_SIGNATURE = 0x80070203
KEY_USAGE_KEY_ENCIPHERMENT = 0x20050203

class TestPf9Cert(TestCase):

    def test_root_ca(self):
        self._do_root_ca('acme')

    def test_root_ca_with_spaces(self):
        try:
            self._do_root_ca('acme inc')
        except:
            return
        raise Exception('Short company names containing spaces should not work')

    def _do_root_ca(self, id):
        days = 100
        tuple1 = pf9cert.create_root_CA(id, 'Acme, Inc.', days)
        for (private_key, cert) in [tuple1, pf9cert.get_CA(id)]:
            c = crypto.load_certificate(crypto.FILETYPE_PEM, cert)
            assert c.get_subject().commonName == id
            not_after = c.get_notAfter()
            not_after = dt.strptime(not_after.decode(),"%Y%m%d%H%M%SZ")
            days_left = (not_after - dt.now()).days
            assert days_left == days or days_left == (days - 1)
            self._verify_key_usage(c, KEY_USAGE_CERT_SIGN)
        pf9cert.remove_CA(id)
        try:
            pf9cert.get_CA(id)
            assert False
        except:
            pass

    def test_signing(self):
        id = 'foo'
        svc = 'hostagent'
        days = 50
        (ca_key, ca_cert) = pf9cert.create_root_CA(id, 'Foo, Inc.', days)
        tuple1 = pf9cert.create_certificate(id, svc, days, for_server=False)
        for (svc_key, svc_cert) in [tuple1, pf9cert.get_certificate(id, svc)]:
            c = crypto.load_certificate(crypto.FILETYPE_PEM, svc_cert)
            assert c.get_subject().commonName == svc
            assert c.get_issuer().commonName == id
            not_after = c.get_notAfter()
            not_after = dt.strptime(not_after.decode(),"%Y%m%d%H%M%SZ")
            days_left = (not_after - dt.now()).days
            assert days_left == days or days_left == (days - 1)
            self._verify_key_usage(c, KEY_USAGE_DIGITAL_SIGNATURE)
        pf9cert.remove_certificate(id, svc)
        try:
            pf9cert.get_certificate(id, svc)
            assert False
        except:
            pass

        # Test server side certificate
        svc = 'broker'
        (key, cert) = pf9cert.create_certificate(id, svc, days, for_server=True)
        c = crypto.load_certificate(crypto.FILETYPE_PEM, cert)
        self._verify_key_usage(c, KEY_USAGE_KEY_ENCIPHERMENT)

    def _verify_key_usage(self, c, key_usage):
        num_extensions = c.get_extension_count()
        assert num_extensions
        for i in range(num_extensions):
            ext = c.get_extension(i)
            short_name = ext.get_short_name()
            data = ext.get_data()
            print ('Found extension %s with length %d' % (short_name, len(data)))
            if short_name.decode() == 'keyUsage':
                assert len(data) == 4
                word = struct.unpack('I', data)[0]
                print ('keyUsage: %s' % hex(word))
                assert word == key_usage
                return
        raise Exception('KeyUsage extension not found')
