#!/bin/python
# Copyright (c) 2016 Platform9 Systems Inc.

import socket
import optparse

def resolve_fqdn(du_fqdn):
    try:
        socket.gethostbyname(du_fqdn)
        print("DNS resolution OK!")
    except socket.gaierror as e:
        print("Cannot resolve {0}: {1}".format(du_fqdn, e))
        exit(1)

def connect_to_host(du_fqdn, port):
    print("Connecting to {0}:{1}".format(du_fqdn, port))
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((du_fqdn, port))
        sock.close()
        print("Connection to {0} succeeded!".format(du_fqdn))
    except socket.error as e:
        print("Error connecting to {0}: {1}".format(du_fqdn, e))
        exit(2)

def connect_to_host_via_proxy(proxy_host, proxy_port, du_fqdn, port):
    print("Connecting to {0}:{1}".format(proxy_host, proxy_port))
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((proxy_host, proxy_port))
        print("Connection to {0}:{1} succeeded!".format(proxy_host,
                                                        proxy_port))
        print("Connecting to {0}:{1}".format(du_fqdn, port))
        sock.send("CONNECT {0}:{1} HTTP/1.0\r\n\r\n".format(du_fqdn,
                                                            port))
        res = sock.recv(1024)
        if "200 connection established" in res.lower():
            print("Connection to {0} via {1} succeeded!".format(du_fqdn,
                                                                proxy_host))
            sock.close()
        else:
            print("Error connecting to {0} via {1}:{2}".format(du_fqdn,
                                                             proxy_host,
                                                             proxy_port))
            sock.close()
            exit(3)
    except socket.error as e:
        print("Error connecting to {0}:{1}: {1}".format(proxy_host,
                                                        proxy_port,
                                                        e))
        exit(3)

def parse_options():
    usage="usage: %prog <command> [args]"
    parser = optparse.OptionParser(usage=usage)
    parser.add_option('--du-fqdn', action='store', dest='du_fqdn',
            help="Fully qualified domain name")

    parser.add_option('--port', action='store', dest='port',
            help="Port number")
    parser.add_option('--proxy-host', action='store', dest='proxy_host',
            help="Proxy host")

    parser.add_option('--proxy-port', action='store', dest='proxy_port',
            help="Port number")

    opts, args = parser.parse_args()
    return vars(opts), args

if __name__ == "__main__":
    options, args = parse_options()
    resolve_fqdn(options['du_fqdn'])
    if options['proxy_host'] is None:
        connect_to_host(options['du_fqdn'], int(options['port']))
    else:
        connect_to_host_via_proxy(options['proxy_host'],
                                  int(options['proxy_port']),
                                  options['du_fqdn'],
                                  int(options['port']))
