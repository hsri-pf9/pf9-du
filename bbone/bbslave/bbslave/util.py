import threading
import os
from six.moves import queue as Queue
from bbslave import certs

PRIVATE_KEY_PEM_FILE = '/etc/pf9/certs/hostagent/key.pem'
CERT_PEM_FILE = '/etc/pf9/certs/hostagent/cert.pem'
CA_PEM_FILE = '/etc/pf9/certs/ca/cert.pem'
CA_DIRECTORY = '/etc/pf9/certs/ca'

CERT_DETAILS_STATUS_SUCCESS = 'successful'
CERT_DETAILS_STATUS_FAILED = 'FAILED'
CERT_DETAILS_STATUS_NOT_QUERIED = 'not-queried'

CERT_REFRESH_STATUS_SUCCESS = 'successful'
CERT_REFRESH_STATUS_INITIATED = 'initiated'
CERT_REFRESH_STATUS_NOT_REFRESHED = 'not-refreshed'
CERT_REFRESH_STATUS_RESTORED = 'failed-restored'
CERT_REFRESH_STATUS_FAILED = 'failed'

fingerprint_path = '/etc/pf9/fingerprint.txt'

cert_info = {}
vouch_present = False
cert_info_q = Queue.Queue()
cert_update_event = threading.Event()

cert_info = {
    'details' : {
        # Possible values of status: not-queried, failed, successful
        'status' : CERT_DETAILS_STATUS_NOT_QUERIED,
        'version' : '',
        'serial_number' : '',
        'start_date' : '',
        'expiry_date' : '',
        'timestamp' : ''
    },
    'refresh_info' : {
        # Possible values of status: not-refreshed, initiated, successful,
        # failed-restored, failed
        'status' : CERT_REFRESH_STATUS_NOT_REFRESHED,
        'message' : '',
        'timestamp' : ''
    }
}

def check_for_cert_data(log):
    """
    This function would get the cert details and cert refresh response from
    the update-cert thread (if available)

    Returns
    Dict containing
    details: Details about the current certificate
    refresh_status: status of cert refresh operation
    """
    global cert_info_q
    global cert_info
    try:
        data = cert_info_q.get_nowait()

        if data['msg'] == 'cert_info':
            cert_info['details'] = data['details']
            log.info('Received cert_info message on the queue.')
        elif data['msg'] == 'cert_update_initiated' or \
                    data['msg'] == 'cert_update_result':
            cert_info['refresh_info'] = data['details']
            log.info('Received {} message on the queue.'.format(data['msg']))
        else:
            log.error('Unknown message type: {} on cert queue'.format(
                data['msg']))
    except Queue.Empty:
        log.debug('cert info queue is empty. Nothing to process')
    except (KeyError, ValueError) as e:
        log.error('Malformed messages on the cert queue. Exception {}'.format(e))
    except Exception as e:
        log.exception('Exception occurred while processing message on queue.')
    finally:
        log.debug('Cert_info: {}'.format(cert_info))
        return cert_info

def check_vouch_connection(vouch_url):
    global vouch_present
    vouch_present = certs.check_connection(vouch_url)

def read_fingerprint():
    if os.path.exists(fingerprint_path):
        with open(fingerprint_path, 'r') as f:
            return f.read().strip()
    else:
        return None