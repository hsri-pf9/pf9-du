
import time
import datetime
import threading
import re
import requests
import os
from socket import gethostname
from six import iteritems

from cryptography import x509
from cryptography.hazmat.backends import default_backend
from six.moves import queue as Queue

from bbslave import certs
from bbslave import util
from bbslave.sysinfo import get_sysinfo, get_host_id

_host_id = get_host_id()

def cert_update_thread(config, log):

    log.info('-------------------------------')
    log.info('Platform9 host agent Cert-Update-Thread started at %s on '\
        'thread %s', datetime.datetime.now(),
            threading.current_thread().ident)

    vouch_url = config.get('hostagent', 'vouch_url') if \
        config.has_option('hostagent', 'vouch_url') else 'http://localhost:8558'
    automatic_cert_refresh_interval_days = int (config.get('hostagent', 'cert_refresh_interval_days')) if \
        config.has_option('hostagent', 'cert_refresh_interval_days') else 90
    cert_info_query_interval_hours = int (config.get('hostagent', 'cert_info_frequency_hours')) if \
        config.has_option('hostagent', 'cert_info_frequency_hours') else 24
    cert_pem_file = config.get('hostagent', 'cert_file') if \
        config.has_option('hostagent', 'cert_file') else util.CERT_PEM_FILE
    ca_pem_file = config.get('hostagent', 'ca_file') if \
        config.has_option('hostagent', 'ca_file') else util.CA_PEM_FILE
    private_key_pem_file = config.get('hostagent', 'private_key_file') if \
        config.has_option('hostagent', 'private_key_file') else \
            util.PRIVATE_KEY_PEM_FILE
    ca_directory = config.get('hostagent', 'ca_directory') if \
        config.has_option('hostagent', 'ca_directory') else \
            util.CA_DIRECTORY

    util.check_vouch_connection(vouch_url)

    if not util.vouch_present:
        log.info('Unable to vouch URL {}.'.format(vouch_url))
        log.info('Cert-Update-Thread exiting')
        return 0

    log.info('Successfully connected to vouch URL {}.'.format(vouch_url))

    # Sleep for 30 seconds for host agent's main thread to start.
    time.sleep(30)

# ---------------------------- Nested functions -------------------------------

    def cert_refresh_needed(cert_expiry_date):
        curr_time = datetime.datetime.now(tz=datetime.timezone.utc)
        expiry_datetime = datetime.datetime.fromtimestamp(cert_expiry_date,
                                    tz=datetime.timezone.utc)
        return (expiry_datetime - curr_time) <= datetime.timedelta(
            days=automatic_cert_refresh_interval_days)

    def process_cert_update_request(new_ca=False):
        """
        Triggers an update of certificates.
        Sends CSR to vouch service via comms. On receiving new certs, it would
        try to update the certs on host and restart the comms service.

        Returns: A dictionary containing status and error message of cert-update
            request.
        """
        resp = {}
        log.debug('Starting process of updating the host certificates')
        resp['msg']  = 'cert_update_result'
        hostname = gethostname()
        if len(hostname):
            common_name = hostname[0:54].rstrip('.') + '-'

        common_name += _host_id[0:8]

        allowed_cn = re.compile("^(([a-zA-Z0-9]|[a-zA-Z0-9][a-zA-Z0-9\-]*"\
            "[a-zA-Z0-9])\.)*([A-Za-z0-9]|[A-Za-z0-9][A-Za-z0-9\-]*[A-Za-z0-9])$")

        if not allowed_cn.match(common_name):
            log.error('CN: {} does not appear to meet the CN requirements for '\
                'the CSR. Rejecting the cert update request.'.format(common_name))
            msg_info = {
                'status' : util.CERT_REFRESH_STATUS_FAILED,
                'message' : 'CN: {} does not appear to meet the CN '\
                    'requirements for the CSR. Rejecting the certificate update '\
                    'request on {}'.format(common_name,
                        datetime.datetime.utcnow().strftime("%c")),
                'timestamp' : datetime.datetime.utcnow().timestamp()
            }
            resp['details'] = msg_info
            return resp

        log.info('Requesting certificates from {} with CN = {}'.format(vouch_url,
            common_name))

        vouch = certs.VouchCerts(vouch_url)
        privatekey, csr = certs.generate_key_and_csr(common_name)
        privatekey = privatekey.decode("utf-8")
        csr = csr.decode("utf-8")
        try:
            cert, ca = vouch.sign_csr(csr, common_name)
            if not cert or not ca:
                log.error('Failed to get new certificates from vouch.')
                msg_info = {
                    'status' : util.CERT_REFRESH_STATUS_FAILED,
                    'message' : 'Failed to get new certificates from vouch on {}'.format(
                        datetime.datetime.utcnow().strftime("%c")),
                    'timestamp' : datetime.datetime.utcnow().timestamp()
                }
                resp['details'] = msg_info
                return resp
        except Exception:
            log.exception('Exception occurred while getting new certificates from vouch')
            msg_info = {
                    'status' : util.CERT_REFRESH_STATUS_FAILED,
                    'message' : 'Failed to get new certificates from vouch on {}'.format(
                        datetime.datetime.utcnow().strftime("%c")),
                    'timestamp' : datetime.datetime.utcnow().timestamp()
                }
            resp['details'] = msg_info
            return resp
        backups = certs.backup_and_save_certs({
            private_key_pem_file: privatekey.encode("utf-8"),
            cert_pem_file: cert.encode("utf-8"),
            ca_pem_file: ca.encode("utf-8")
        })

        if new_ca:
            log.info('Starting process of updating the CA certificates')
            try:
                ca_list = vouch.get_all_ca()
                certs.place_new_CAs(ca_pem_file, ca_list)
            except requests.exceptions.HTTPError as e:
                if e.response.status_code == 404:
                    log.info("Vouch doesn't have endpoint to list CAs")
                else:
                    log.exception('Exception occurred while fetching CA List')

        log.info ('Updating pf9-comms with new certificates.')
        if certs.restart_comms_sidekick() and certs.check_connection():
            # Note that we check connection only through comms. And assume
            # sidekick connectivity on restart will work if comms works.
            log.info('Refreshed host certificates and verified controller '\
                'connection.')
            msg_info = {
                'status' : util.CERT_REFRESH_STATUS_SUCCESS,
                'message' : 'Host certs refreshed successfully on {}'.format(
                    datetime.datetime.utcnow().strftime("%c")),
                'timestamp' : datetime.datetime.utcnow().timestamp()
            }
            resp['details'] = msg_info
            return resp
        else:
            log.error('Failed to bring up pf9_comms with new host certificates, '\
                'restoring old ones.')
            certs.restore_backups(backups)
            if certs.restart_comms_sidekick() and certs.check_connection():
                # Note that we check connection only through comms. And assume
                # sidekick connectivity on restart will work if comms works.
                log.info('Restored old certificates successfully and verified '\
                    'controller connection.')
                msg_info = {
                    'status' : util.CERT_REFRESH_STATUS_RESTORED,
                    'message' : 'Certificate refresh failed. '\
                        'Restored old certificates and verified controller '\
                        'connection on {}'.format(
                            datetime.datetime.utcnow().strftime("%c")),
                    'timestamp' : datetime.datetime.utcnow().timestamp()
                }
                resp['details'] = msg_info
                return resp
            else:
                log.critical('Restoration of old certificates failed. We are in '\
                    'a bad state.')
                # At this point comms won't be able to communicate with the DU.
                # Just return None.
                return None

    def _get_cert_info(certs_file):
        """
        Retrieves cert info like version, serial number, expiry date.
        retruns a dict containing this info.
        """
        cert_details = {}
        try:
            log.debug("getting the certificate info for cert file : {}".format(
                certs_file))
            with open(certs_file, 'rb') as f:
                certstr = f.read()

            cert = x509.load_pem_x509_certificate(certstr, default_backend())

            cert_details['status'] = util.CERT_DETAILS_STATUS_SUCCESS
            cert_details['version'] = str(cert.version)
            cert_details['serial_number'] = cert.serial_number
            cert_details['expiry_date'] = cert.not_valid_after.timestamp()
            cert_details['start_date'] = cert.not_valid_before.timestamp()
            cert_details['timestamp'] = datetime.datetime.utcnow().timestamp()
            return cert_details
        except Exception :
            log.exception("Exception occurred while getting certificate info for cert file : {}".format(
                certs_file))
            cert_details['status'] = util.CERT_DETAILS_STATUS_FAILED
            cert_details['version'] = ''
            cert_details['serial_number'] = ''
            cert_details['expiry_date'] = ''
            cert_details['start_date'] = ''
            cert_details['timestamp'] = ''
            return cert_details

    def new_ca_cert_available():
        """
        Checks if local CAs are in sync with CAs returned by vouch
        """
        vouch = certs.VouchCerts(vouch_url)
        try:
            ca_list = vouch.get_all_ca()
            vouch_ca = set()
            for certstr in ca_list:
                certstr = certstr.encode('UTF-8')
                cert_data = x509.load_pem_x509_certificate(certstr, default_backend())
                vouch_ca.add(cert_data.serial_number)

            local_ca = set()
            for ca_file in os.listdir(ca_directory):
                f = os.path.join(ca_directory, ca_file)
                ca_cert_data = _get_cert_info(f)
                if ca_cert_data['status'] == util.CERT_DETAILS_STATUS_SUCCESS:
                    local_ca.add(ca_cert_data['serial_number'])

            if vouch_ca.issubset(local_ca):
                log.info('CA list returned by vouch is subset of CAs on host. No CA update needed.')
                return False
            else:
                log.info('CA list returned by vouch is NOT a subset of CAs on host. CA update needed.')
                return True

        except requests.exceptions.HTTPError as e:
            if e.response.status_code == 404:
                log.info("Vouch doesn't have endpoint to list CAs")
                return False
            else:
                log.exception('Exception occurred while fetching list of CAs from vouch')


# -------------------------- End of nested functions --------------------------
    while True:
        log.debug('Cert-Update thread is getting the certificate info')
        cert_data = _get_cert_info(cert_pem_file)
        if cert_data:
            # check if cert refresh is needed
            try:
                cert_expiry_date = cert_data['expiry_date']
                needs_cert_refresh = cert_refresh_needed(cert_expiry_date)
                new_ca = new_ca_cert_available()
                if needs_cert_refresh or new_ca:
                    # Put a message on the queue that certs are being updated.
                    # This will be sent to bbmaster by the main thread.
                    resp = {}
                    msg_info = {
                        'status' : util.CERT_REFRESH_STATUS_INITIATED,
                        'message' : 'Initiated automated host certificate '\
                            ' update process on {}'.format(
                                datetime.datetime.utcnow().strftime("%c")),
                        'timestamp' : datetime.datetime.utcnow().timestamp()
                    }
                    resp['msg'] = 'cert_update_initiated'
                    resp['details'] = msg_info

                    util.cert_info_q.put(resp, timeout=10)

                    response = process_cert_update_request(new_ca)

                    # Now put the cert update response in the queue
                    util.cert_info_q.put(response, timeout=10)

                # If certs are refreshed, get the details of refreshed certs.
                if needs_cert_refresh:
                    cert_data = _get_cert_info(cert_pem_file)

                cert_msg = {}
                cert_msg['msg']  = 'cert_info'
                cert_msg['details'] = cert_data

                util.cert_info_q.put(cert_msg, timeout=10)

            except Queue.Full:
                log.error('Host agent main thread is not reading the '\
                    'messages from the queue.')
            except Exception:
                log.exception('Exception occurred while processing certificates')
        else:
            log.error('Failed to get details of the certificate {}'.format(
                cert_pem_file))

        # Wait on the cert update event with a timeout specified.
        log.info('Cert Update thread is now waiting on an event with timeout'\
            ' of {} hours'.format(cert_info_query_interval_hours))
        event_received = util.cert_update_event.wait(cert_info_query_interval_hours*60*60)
        if event_received:
            try:
                log.debug('Received cert_update event.')
                util.cert_update_event.clear()
                cert_msg = {}
                msg_info = {
                    'status' : util.CERT_REFRESH_STATUS_INITIATED,
                    'message' : 'Initiated forced host certificate update '\
                        'process on {}'.format(
                        datetime.datetime.utcnow().strftime("%c")),
                    'timestamp' : datetime.datetime.utcnow().timestamp()
                }
                cert_msg['msg'] = 'cert_update_initiated'
                cert_msg['details'] = msg_info

                util.cert_info_q.put(cert_msg, timeout=10)

                # check if CA refresh is also needed. Intent is to invoke
                # CA refresh only if needed.
                ca_refresh_needed = new_ca_cert_available()
                response = process_cert_update_request(ca_refresh_needed)

                # Now put the cert update response in the queue
                util.cert_info_q.put(response, timeout=10)

            except Queue.Full:
                log.error('Host agent main thread is not reading the messages'\
                    ' from the queue.')
            except Exception:
                log.exception('Exception occurred while processing update cert '\
                    'request')
        else:
            # Timeout occurred, check the cert details
            log.debug('Timed-out from the event wait.')
            continue
