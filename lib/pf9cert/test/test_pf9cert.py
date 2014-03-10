# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights Reserved.

from unittest import TestCase

import pf9cert
from OpenSSL import crypto
from datetime import datetime as dt

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
            not_after = dt.strptime(not_after,"%Y%m%d%H%M%SZ")
            days_left = (not_after - dt.now()).days
            assert days_left == days or days_left == (days - 1)
        pf9cert.remove_CA(id)
        try:
            pf9cert.get_CA(id)
            assert False
        except:
            pass

    def test_signing(self):
        id = 'foo'
        svc = 'broker'
        days = 50
        (ca_key, ca_cert) = pf9cert.create_root_CA(id, 'Foo, Inc.', days)
        tuple1 = pf9cert.create_certificate(id, svc, days)
        for (svc_key, svc_cert) in [tuple1, pf9cert.get_certificate(id, svc)]:
            c = crypto.load_certificate(crypto.FILETYPE_PEM, svc_cert)
            assert c.get_subject().commonName == svc
            assert c.get_issuer().commonName == id
            not_after = c.get_notAfter()
            not_after = dt.strptime(not_after,"%Y%m%d%H%M%SZ")
            days_left = (not_after - dt.now()).days
            assert days_left == days or days_left == (days - 1)
        pf9cert.remove_certificate(id, svc)
        try:
            pf9cert.get_certificate(id, svc)
            assert False
        except:
            pass
