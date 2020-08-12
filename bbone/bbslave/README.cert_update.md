## Cert update thread
A new thread has been introduced for querying host certificate info and to
update the host certificates when they are close to expiry. Communication
between main thread of the hostagent and cert update thread happens over a
queue. While sending the status message, it checks if there is any new info on
the queue. If yes, it will send the update as a part of status message.
Once the cert update thread has queried the certificates it waits for on an
event from hostahent main thread or a timeout to occur.

There are two ways by which cert refresh can happen on the host
1. Automated update: This is initiated by the hostagent itself when host certs
                    are close to expiry (default is 90 days before cert expiry
                    date)
2. Forceful update: This is initiated from the DU. On receiving cert_update
                    command, hostagent would try to update the certs without
                    worrying about expiry date.

Following are the exchange of messages between hostagent main thread and cert
update thread:
1. cert_info : Details about host certs
2. cert_update_initiated: Host cert refresh has been initiated
3. cert_update_result: Result of host cert refresh operation.

For forcefully refreshing the certs, hostagent main thread would set an event,
which cert update thread is waiting on.

Following is the data that is published on the queue used for communication
between host agent threads (main thread and cert update thread):
{
    "details": {
        "status": "successful",
        "start_date": 1597402962.0,
        "expiry_date": 1628938992.0,
        "serial_number": 362748187225457386532088060804963813485895720515,
        "timestamp": 1597403034.263916,
        "version": "Version.v3"
    },
    "refresh_info": {
        "status": "successful",
        "message": "Host certs refreshed successfully on Fri Aug 14 11:15:04 2020",
        "timestamp": 1597403704.790267
    }
}

Possible values for status field under details:
1. not-queried: Host cert info is not yet queried
2. failed: Host cert query has failed
3. successful: Host cert info has been successfully queried.

Possible values for status field under refresh_info:
1. not-refreshed: Host certs are not yet refreshed
2. initiated: Host cert refresh has been initiated
3. successful: Host cert refresh has been successful and comms-DU communication
                is working fine.
4. failed-restored: Host cert refresh failed but old certs are restored and
                comms-DU communication is working fine.
5. failed: Host cert refresh has failed
