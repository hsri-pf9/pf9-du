# Copyright (c) Platform9 Systems. All rights reserved.

import datetime
import json
import logging
import os
import time

from integration.test_util import BaseTestCase
from pf9lab import du, resource_manager
from pf9lab.retry import retry
from pf9lab.testbeds.common import (change_config_value_on_host,
                                    remove_config_value_on_host,
                                    restart_services_on_host)
from pf9lab.testbeds.loader import load_testbed
from pf9lab.testbeds.pmk_testbed import PmkTestbed
from proboscis import after_class, before_class, test

log = logging.getLogger(__name__)

hostagent_config_file = '/etc/pf9/hostagent.conf'
conf_section = 'hostagent'
conf_parameter = 'cert_refresh_interval_days'
value = '366'

CERT_REFRESH_STATUS_SUCCESS = 'successful'
CERT_REFRESH_STATUS_INITIATED = 'initiated'
CERT_REFRESH_STATUS_NOT_REFRESHED = 'not-refreshed'
CERT_REFRESH_STATUS_RESTORED = 'failed-restored'
CERT_REFRESH_STATUS_FAILED = 'failed'

CERT_DETAILS_STATUS_SUCCESS = 'successful'
CERT_DETAILS_STATUS_FAILED = 'FAILED'
CERT_DETAILS_STATUS_NOT_QUERIED = 'not-queried'

hostagent_service = ['pf9-hostagent']

NUMBER_OF_HOSTS = 2
HOST_CERT_EXPIRY_PERIOD_SEC = 31536030.00


@test(groups=["integration"])
class TestHostCertRefresh(BaseTestCase):

    @before_class
    def setUp(self):
        testbed_file = os.getenv("TESTBED")
        self.assertTrue(testbed_file)
        self._tb = load_testbed(testbed_file)
        self.assertTrue(isinstance(self._tb, PmkTestbed))
        auth_info = du.auth.login(
            "https://%s" % self._tb.du_fqdn(),
            self._tb.du_user(),
            self._tb.du_pass(),
            "service",
        )
        self.token = auth_info["access"]["token"]["id"]
        self.host_ips = self._tb.all_host_ips()
        self.assertEqual(len(self.host_ips), NUMBER_OF_HOSTS)

    @after_class
    def tearDown(self):
        pass

    def _cleanup(self, host_id):
        """
        Cleanups files created during test run
        """
        pass

    @retry(max_wait=240,
           interval=60,
           is_ready=lambda cert_info: cert_info['details']['status'] ==
           'successful',
           log=log)
    def _get_cert_info_from_resmgr(self, du_fqdn, keystone_token, host_id):
        """
        Gets the cert info from the resource manager cert endpoint.
        Retry for 4 times to get the cert info from host
        """
        cert_info = resource_manager.get_host_cert_info(
            du_fqdn, keystone_token, host_id)
        return cert_info

    def _populate_cert_info_single_host(self, host_id):
        """
        Get the cert info of a particular host

        param host_id: id of the host for which cert info needs to be queried
        """
        self.assertTrue(host_id is not None)
        cert_info = self._get_cert_info_from_resmgr(self._tb.du_fqdn(),
                                                    self._tb.du_token(),
                                                    host_id)
        return cert_info

    def _populate_host_cert_info(self):
        """
        Get the cert info of all the hosts registered with resource manager
        """
        # Get the hosts registered with resource manager
        resmgr_hosts = resource_manager.get_resmgr_hosts(
            self._tb.du_fqdn(), self._tb.du_token())

        cert_info = {}
        for host in resmgr_hosts:
            host_id = host['id']
            self.assertTrue(host_id is not None)
            log.info("Requesting cert info from host: %s" % host_id)
            cert_info[host_id] = self._get_cert_info_from_resmgr(
                self._tb.du_fqdn(), self._tb.du_token(), host_id)

        return cert_info

    def _force_host_cert_refresh(self, refresh_all=False):
        """
        Trigger a forced cert refresh on the hosts
        This function will trigger forced host cert refrsh by calling PUT on
        an API endpoint exposed by resource manager. By default it will trigger
        cert refresh on alternate hosts from hosts registered with resource
        manager (unless specified through input parameter).

        param refresh_all: True if cert refresh needs to be triggered on all
                           hosts.
        """
        # Get the hosts registered with resource manager
        resmgr_hosts = resource_manager.get_resmgr_hosts(
            self._tb.du_fqdn(), self._tb.du_token())

        self.assertEqual(len(resmgr_hosts), NUMBER_OF_HOSTS)

        host_cert_refresh_triggered = []
        host_cert_refresh_not_triggered = []
        count = 0

        for host in resmgr_hosts:
            host_id = host['id']
            self.assertTrue(host_id is not None)

            # Trigger cert refresh on the alternate hosts unless specified
            # in the input parameter
            if count % 2 == 0:
                host_cert_refresh_triggered.append(host_id)
                resource_manager.force_host_cert_refresh(
                    self._tb.du_fqdn(), self._tb.du_token(), host_id)
            else:
                host_cert_refresh_not_triggered.append(host_id)

            if refresh_all == False:
                count += 1

        log.info('Cert refresh successfully triggered on hosts: {}'.format(
            host_cert_refresh_triggered))
        log.info('Cert refresh is not triggered on hosts: {}'.format(
            host_cert_refresh_not_triggered))

        return host_cert_refresh_triggered, host_cert_refresh_not_triggered

    def _trigger_automated_host_cert_refresh(self):
        """
        Set a parameter in the hostagent.conf file which will trigger host
        cert upgrade on pf9-hostagent restart.
        """

        self.assertEqual(len(self.host_ips), NUMBER_OF_HOSTS)

        for ip in self.host_ips:
            log.info('Setting value of {} parameter under {} section to true '\
                'in hostagent.conf file on host with IP: {}'.format(
                conf_parameter,conf_section, ip))
            rc = change_config_value_on_host(
                host_ip=ip,
                config_file_path=hostagent_config_file,
                section=conf_section,
                parameter=conf_parameter,
                value=value)
            self.assertTrue(rc)
            log.info(
                'Restarting hostagent service on host with IP: {}'.format(ip))
            restart_services_on_host(ip, hostagent_service)

    def _disable_auto_cert_refresh(self):
        """
        Remove config parameter from the hostagent.conf file to disable automated
        host cert upgrade on pf9-hostagent restart.
        """
        for ip in self.host_ips:
            log.info('Removing parameter {} under {} section from hostagent.conf'\
                ' file on host with IP: {}'.format(conf_parameter,
                conf_section, ip))
            rc = remove_config_value_on_host(
                host_ip=ip,
                config_file_path=hostagent_config_file,
                section=conf_section,
                option=conf_parameter)
            self.assertTrue(rc)
            log.info(
                'Restarting hostagent service on host with IP: {}'.format(ip))
            restart_services_on_host(ip, hostagent_service)

    def _compare_refreshed_certs(self, old_cert_info, host_id_list):
        """
        Compare old and refreshed certs of given hosts in host list
        This function will query resource manager every 15 seconds with a
        timeout of 28 cycles (7 minutes) till it receives cert refresh status
        as successful.

        param old_cert_info: dict containing old cert info
        param host_list: list having host_ids for which cert info needs to be checked.
        """
        cert_refresh_complete = True
        new_cert_info = {}
        if not len(host_id_list):
            log.info('input host list is empty. Nothing to check.')
            return
        for _ in range(28):
            # Run through the host list and get the cert refresh status
            cert_refresh_complete = True
            for host_id in host_id_list:
                #Get the cert info of the host
                new_cert_info[host_id] = self._populate_cert_info_single_host(
                    host_id)
                refresh_status = new_cert_info[host_id]['refresh_info'][
                    'status']
                log.info('Refresh status of host cert on host {} is {}'.format(
                    host_id, refresh_status))
                # Validate cert refresh has not failed on the host.
                self.assertNotEqual(refresh_status,
                                    CERT_REFRESH_STATUS_RESTORED)
                self.assertNotEqual(refresh_status, CERT_REFRESH_STATUS_FAILED)
                if refresh_status != CERT_REFRESH_STATUS_SUCCESS:
                    cert_refresh_complete = False
                    log.info(
                        'Cert refresh is not yet complete on the host: {}'.
                        format(host_id))
                else:
                    # Cert refresh process has been completed successfully.
                    # Hostagent would send updated cert info in next heartbeat
                    # cycle. Mark the cert refresh process complete only after
                    # receiving updated cert info from hostagent.
                    cert_query_status = new_cert_info[host_id]['details'][
                        'status']
                    cert_query_ts = new_cert_info[host_id]['details'][
                        'timestamp']
                    log.info('Cert refresh on host: {} is successful. Now '\
                        'checking to get updated cert details.'.format(host_id))
                    if cert_query_status != CERT_DETAILS_STATUS_SUCCESS or \
                        old_cert_info[host_id]['details']['timestamp'] == cert_query_ts:
                        cert_refresh_complete = False

            if cert_refresh_complete == True:
                log.info(
                    'Cert refresh successfully completed on all the hosts.')
                break

            # Cert update is not complete on all the hosts.
            # Sleep for 15 seconds before next query
            time.sleep(15)

        # Check if we have crossed threshold of successful cert refresh time
        if cert_refresh_complete != True:
            self.fail('Cert refresh process did not complete in expected time')

        for host_id in host_id_list:
            # Validate host id is present in old cert info
            self.assertTrue(host_id in old_cert_info)

            # Validate that cert version is equal
            self.assertEqual(old_cert_info[host_id]['details']['version'],
                             new_cert_info[host_id]['details']['version'])

            # Validate that the cert serial number is not equal
            self.assertNotEqual(
                old_cert_info[host_id]['details']['serial_number'],
                new_cert_info[host_id]['details']['serial_number'])

            # Validate that the cert start date is not equal
            self.assertNotEqual(
                old_cert_info[host_id]['details']['start_date'],
                new_cert_info[host_id]['details']['start_date'])

            # Validate that the cert expiry date is not equal
            self.assertNotEqual(
                old_cert_info[host_id]['details']['expiry_date'],
                new_cert_info[host_id]['details']['expiry_date'])

            # Convert timestamp to datetime to ensure that it has a valid value
            try:
                old_exp_date = datetime.datetime.fromtimestamp(
                    old_cert_info[host_id]['details']['expiry_date'],
                    tz=datetime.timezone.utc)
                old_start_date = datetime.datetime.fromtimestamp(
                    old_cert_info[host_id]['details']['start_date'],
                    tz=datetime.timezone.utc)
            except ValueError:
                self.fail('Old cert start/expiry date not in a valid datetime'\
                    ' format')

            # Convert timestamp to datetime to ensure that it has a valid value
            try:
                refreshed_exp_date = datetime.datetime.fromtimestamp(
                    new_cert_info[host_id]['details']['expiry_date'],
                    tz=datetime.timezone.utc)
                refreshed_start_date = datetime.datetime.fromtimestamp(
                    new_cert_info[host_id]['details']['start_date'],
                    tz=datetime.timezone.utc)
            except ValueError:
                self.fail('Refreshed cert expiry/start date not in a valid '\
                    'datetime format')

            # Check validaity of cert expiry and start date
            self.assertTrue(refreshed_exp_date > old_exp_date)
            self.assertTrue(refreshed_start_date > old_start_date)
            self.assertEqual((old_exp_date - old_start_date),
                             (refreshed_exp_date - refreshed_start_date))
            self.assertTrue((refreshed_exp_date -
                             refreshed_start_date) == datetime.timedelta(
                                 seconds=HOST_CERT_EXPIRY_PERIOD_SEC))

            log.info(
                'Refreshed certs successfully validated for host: {}'.format(
                    host_id))

    def _compare_non_refreshed_certs(self, old_cert_info, host_id_list):
        """
        Ensure that certs do not change on hosts on which certs refresh action
        is not triggered.
        This function will query resource manager every 15 seconds with a
        timeout of 12 cycles (3 minutes) and compare that cert info of old
        certs and queried certs is same.

        param old_cert_info: dict containing old cert info
        param host_id_list:  list of host ids for which cert info needs to be
                             checked.
        """

        new_cert_info = {}
        for _ in range(12):
            for host_id in host_id_list:
                #Get the cert info of the host
                new_cert_info[host_id] = \
                        self._populate_cert_info_single_host(host_id)

                refresh_status = new_cert_info[host_id]['refresh_info'][
                    'status']
                log.info('Refresh status of host cert on host {} is {}'.format(
                    host_id, refresh_status))
                self.assertEqual(
                    refresh_status,
                    old_cert_info[host_id]['refresh_info']['status'])
                self.assertNotEqual(refresh_status, CERT_REFRESH_STATUS_FAILED)

            # Sleep for 15 seconds before next query
            time.sleep(15)

        for host_id in host_id_list:
            # Validate host id is present in old cert info
            self.assertTrue(host_id in old_cert_info)

            # Validate that cert version is equal
            self.assertEqual(old_cert_info[host_id]['details']['version'],
                             new_cert_info[host_id]['details']['version'])

            # Validate that the cert serial number is equal
            self.assertEqual(
                old_cert_info[host_id]['details']['serial_number'],
                new_cert_info[host_id]['details']['serial_number'])

            # Validate that the cert start date is equal
            self.assertEqual(old_cert_info[host_id]['details']['start_date'],
                             new_cert_info[host_id]['details']['start_date'])

            # Validate that the cert expiry date is equal
            self.assertEqual(old_cert_info[host_id]['details']['expiry_date'],
                             new_cert_info[host_id]['details']['expiry_date'])

            # Convert timestamp to datetime to ensure that it has a valid value
            try:
                old_exp_date = datetime.datetime.fromtimestamp(
                    old_cert_info[host_id]['details']['expiry_date'],
                    tz=datetime.timezone.utc)
                old_start_date = datetime.datetime.fromtimestamp(
                    old_cert_info[host_id]['details']['start_date'],
                    tz=datetime.timezone.utc)
            except ValueError:
                self.fail('Old cert start / expiry date not in valid datetime'\
                    ' format')

            # Convert timestamp to datetime to ensure that it has a valid value
            try:
                refreshed_exp_date = datetime.datetime.fromtimestamp(
                    new_cert_info[host_id]['details']['expiry_date'],
                    tz=datetime.timezone.utc)
                refreshed_start_date = datetime.datetime.fromtimestamp(
                    new_cert_info[host_id]['details']['start_date'],
                    tz=datetime.timezone.utc)
            except ValueError:
                self.fail('Refreshed cert expiry / start date not in a valid '\
                    'datetime format')

            log.info('Validation successful. Host cert refresh not triggered '\
                'on the host: {}'.format(host_id))

    def _validate_cert_info(self, cert_info):
        """
        Validate the cert_info structure privided
        This function verifies that the cert info provided has Version,
        serial number, start and expiry date in a valid format

        param cert_info: dict containing host cert info
        """
        # Validate we have cert_info for all the hosts (currently 2)
        self.assertEqual(len(cert_info), NUMBER_OF_HOSTS)

        for host_id in cert_info.keys():
            # Validate cert query status
            self.assertTrue('status' in cert_info[host_id]['details'])
            self.assertEqual('successful',
                             cert_info[host_id]['details']['status'])

            # Validate version
            self.assertTrue('version' in cert_info[host_id]['details'])
            self.assertNotNone(cert_info[host_id]['details']['version'])

            # Validate serial number
            self.assertTrue('serial_number' in cert_info[host_id]['details'])
            self.assertNotNone(cert_info[host_id]['details']['serial_number'])

            # Validate start date
            self.assertTrue('start_date' in cert_info[host_id]['details'])
            self.assertNotNone(cert_info[host_id]['details']['start_date'])
            try:
                start_date = datetime.datetime.fromtimestamp(
                    cert_info[host_id]['details']['start_date'],
                    tz=datetime.timezone.utc)
            except ValueError:
                self.fail('Cert start date not in valid format')

            # Validate cert expiry date
            self.assertTrue('expiry_date' in cert_info[host_id]['details'])
            self.assertNotNone(cert_info[host_id]['details']['expiry_date'])
            try:
                exp_date = datetime.datetime.fromtimestamp(
                    cert_info[host_id]['details']['expiry_date'],
                    tz=datetime.timezone.utc)
            except ValueError:
                self.fail('Cert expiry date not in valid format')

            # Validate that start date is after expiry date
            self.assertTrue(exp_date > start_date)

            self.assertEqual(
                (exp_date - start_date),
                datetime.timedelta(seconds=HOST_CERT_EXPIRY_PERIOD_SEC))

            log.info(
                "Cert info validated successfully for host {}".format(host_id))

    @test
    def test_get_cert_info(self):
        """
        Get cert info from the hosts and verify that the cert info provided
        by the host has all required fields.
        """
        log.info("Starting test for validating cert info query")
        host_cert_info = self._populate_host_cert_info()
        self._validate_cert_info(host_cert_info)

    @test(runs_after=[test_get_cert_info])
    def test_force_cert_update(self):
        """
        Test the force refresh of host certs.
        """
        log.info("Starting test for validating forced cert update")
        # Get the cert info of all the hosts with resource manager
        host_cert_info = self._populate_host_cert_info()

        # Trigger host cert refresh
        hosts_cert_refreshed, hosts_cert_not_refreshed = \
                                self._force_host_cert_refresh()

        # Ensure that cert refresh is successful on the hosts on which it was
        # triggered
        self._compare_refreshed_certs(host_cert_info, hosts_cert_refreshed)

        # Ensure that cert refresh is not triggered and cert info sent by
        # hostagent matches with old cert info
        self._compare_non_refreshed_certs(host_cert_info,
                                          hosts_cert_not_refreshed)

    @test(runs_after=[test_force_cert_update])
    def test_automated_cert_update(self):
        """
        Test the automated refresh of host certs.
        """
        log.info("Starting test for validating automated cert refresh")
        # Get the cert info of the hosts
        host_cert_info = self._populate_host_cert_info()

        # Trigget automated cert update on all hosts
        self._trigger_automated_host_cert_refresh()

        # Populate list of all the host ids
        hosts_cert_refreshed = [host_id for host_id in host_cert_info]

        self._compare_refreshed_certs(host_cert_info, hosts_cert_refreshed)
        self._disable_auto_cert_refresh()

    def all_host_ips(self):
        return [host['ip'] for host in self.hosts]
