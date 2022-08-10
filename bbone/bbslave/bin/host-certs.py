# Copyright (c) 2018 Platform9 Systems Inc. All Rights Reserved.

import logging
import os
import pwd
import sys

from argparse import ArgumentParser
from bbslave import certs

logging.basicConfig(
        filename='/var/log/pf9/hostagent-certs.log',
        level=logging.DEBUG,
        format='[%(asctime)s] %(name)-12s %(levelname)-8s %(message)s')

def _can_sign(args):
    vouch = certs.VouchCerts(args.vouch_url, args.keystone_token)
    return 0 if vouch.supports_v1() else 1

def _isroot():
    uid = pwd.getpwnam('root')[2]
    return os.getuid() == uid

def _refresh(args):
    print (('Requesting certs from %s...' % args.vouch_url))
    vouch = certs.VouchCerts(args.vouch_url, args.keystone_token)
    privatekey, csr = certs.generate_key_and_csr(args.common_name)
    privatekey = privatekey.decode("utf-8")
    csr = csr.decode("utf-8")
    cert, ca = vouch.sign_csr(csr, args.common_name)
    backups = certs.backup_and_save_certs({
        args.privatekey: privatekey.encode("utf-8"),
        args.cert: cert.encode("utf-8"),
        args.cacert: ca.encode("utf-8")
    })

    print ('Updating pf9-comms with new certs...')
    if certs.restart_comms_sidekick() and certs.check_connection():
        # Note that we check connection only through comms. And assume
        # sidekick connectivity on restart will work if comms works.
        print ('Refreshed host certs and verified controller connection.')
        return 0
    else:
        sys.stderr.write('Failed to bring up pf9_comms with new certs, '
                         'restoring old ones.\n')
        certs.restore_backups(backups)
        if certs.restart_comms_sidekick() and certs.check_connection():
            # Note that we check connection only through comms. And assume
            # sidekick connectivity on restart will work if comms works.
            sys.stderr.write('Restored old certificates and successfully '
                             'reconnected... Done\n')
            return 1
        else:
            sys.stderr.write('Restoration of old keys failed. This is bad\n')
        return 2

def parse_args():
    common = ArgumentParser()
    common.add_argument('--vouch-url', required=True, help='vouch url')
    common.add_argument('--keystone-token',
                        help='keystone token, needed when using the public '
                             'vouch endpoint.')
    parser = ArgumentParser(prog='host-certs')
    subparsers = parser.add_subparsers()

    can_sign_parser = subparsers.add_parser('can-sign',
                                            parents=[common],
                                            conflict_handler='resolve')
    can_sign_parser.set_defaults(func=_can_sign)

    sign_parser = subparsers.add_parser('refresh',
                                        parents=[common],
                                        conflict_handler='resolve')
    sign_parser.set_defaults(func=_refresh)
    sign_parser.add_argument('--common-name', default='hostagent',
                             help='common name, default \'hostagent\'.')
    sign_parser.add_argument('--cacert',
                             default='/etc/pf9/certs/ca/cert.pem',
                             help='output file for the ca certificate, '
                                  'default \'/etc/pf9/certs/ca/cert.pem\'.')
    sign_parser.add_argument('--cert',
                             default='/etc/pf9/certs/hostagent/cert.pem',
                             help='output file for the signed hostagent '
                                  'certificate, default '
                                  '\'/etc/pf9/certs/hostagent/cert.pem\'.')
    sign_parser.add_argument('--privatekey',
                             default='/etc/pf9/certs/hostagent/key.pem',
                             help='output file for the hostagent private key '
                                  'file, default '
                                  '\'/etc/pf9/certs/hostagent/key.pem\'.')

    return parser.parse_args()

def main():
    if not _isroot():
        sys.stderr.write('You must be root to run this script.\n')
        return 1
    args = parse_args()
    return args.func(args)

if __name__ == '__main__':
    sys.exit(main())
