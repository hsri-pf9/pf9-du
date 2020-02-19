import threading
from six.moves import queue as Queue
from bbslave import certs


PRIVATE_KEY_PEM_FILE = '/etc/pf9/certs/hostagent/key.pem'
CERT_PEM_FILE = '/etc/pf9/certs/hostagent/cert.pem'
CA_PEM_FILE = '/etc/pf9/certs/ca/cert.pem'

cert_info = {}
vouch_present = False
cert_info_q = Queue.Queue()
cert_update_event = threading.Event()

cert_info['cert_details'] = 'Host certificate data not yet queried.'
cert_info['cert_refresh_status'] = 'Host certificate refresh status not yet '\
    'queried.'
cert_info['cert_refresh_details'] = 'Host certificate refresh details not yet '\
    'available.'

def check_for_cert_data(log):
    """
    This function would get the cert details and cert refresh response from
    the update-cert thread (if available)

    Returns
    Dict containing
    cert_data: Details about the current certificate
    cert_refresh_status: status of cert refresh operation
            initiated: Cert refresh operation was initiated
            sucessful: Cert refresh opeation was successful
            restored: Cert refresh failed but restored old certs
    cert_refresh_details: Details about the operation
    """
    global cert_info_q
    global cert_info
    try:
        data = cert_info_q.get_nowait()

        if data['msg'] == 'cert_info':
            cert_info['cert_details'] = data['details']
            log.info('Received cert_info message on the queue.')
        elif data['msg'] == 'cert_update_initiated' or \
                    data['msg'] == 'cert_update_result':
            cert_info['cert_refresh_status'] = data['status']
            cert_info['cert_refresh_details'] = data['details']
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
        log.debug('Cert_data: {} status: {}, details: {}'.format(
            cert_info['cert_details'], cert_info['cert_refresh_status'],
            cert_info['cert_refresh_details']))
        return cert_info

def check_vouch_connection(vouch_url):
    global vouch_present
    vouch_present = certs.check_connection(vouch_url)