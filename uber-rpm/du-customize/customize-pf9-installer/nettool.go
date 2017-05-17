/*
 *  Copyright (c) 2017 Platform9 Systems. All rights reserved
 *
 *  This is a Golang implementation of
 *  pf9-du/uber-rpm/du-customize/customize-pf9-installer/nettool.py
 *
 *  Please note that the binary is on the order of 3MB.
 *
 *  To link statically (no significant change in binary size):
 *  CGO_ENABLED=0 go build -installsuffix cgo nettool.go
 *
 */

package main

import (
	"bufio"
	"flag"
	"fmt"
	"log"
	"net"
	"os"
	"strings"
)

func dial (host string, port string) (net.Conn, error) {

	host_and_port := fmt.Sprintf ("%s:%s", host, port)
	log.Printf ("Connecting to %s", host_and_port)

	conn, err := net.Dial ("tcp", host_and_port)
	if err != nil {
		if strings.Contains (err.Error(), "no such host") {
			log.Printf ("Cannot resolve %s: %s", host, err)
			os.Exit (1)
		}
	}
	log.Print ("DNS resolution OK!")
	return conn, err
}

func connect_to_host (du_fqdn string, port string) int {

	conn, err := dial (du_fqdn, port)
	if err != nil {
		log.Printf ("Error connecting to %s: %s", du_fqdn, err)
	} else {
		log.Printf ("Connection to %s succeeded!", du_fqdn)
		conn.Close()
	}

	if err == nil {
		return 0
	}
	return 2
}

func connect_to_host_via_proxy (proxy_host string, proxy_port string, du_fqdn string, port string) int {

	success := false

	host_and_port := fmt.Sprintf ("%s:%s", proxy_host, proxy_port)

	conn, err := dial (proxy_host, proxy_port)
	if err != nil {
		log.Printf ("Error connecting to %s: %s", host_and_port, err)
	} else {
		log.Printf ("Connection to %s succeeded!", host_and_port)
		text := fmt.Sprintf ("CONNECT %s:%s HTTP/1.0\r\n\r\n", du_fqdn, port)
		fmt.Fprintf (conn, text)
		message, _ := bufio.NewReader(conn).ReadString('\n')
		if strings.Contains (strings.ToLower (message), "200 connection established") {
			log.Printf ("Connection to %s via %s:%s succeeded!", du_fqdn, proxy_host, proxy_port)
			success = true
		} else {
			log.Printf ("Error connecting to %s via %s:%s (%s)", du_fqdn, proxy_host, proxy_port, strings.TrimSpace (message))
		}
		conn.Close()
	}

	if success {
		return 0
	}
	return 3
}

func main() {

	du_fqdn := flag.String ("du-fqdn", "", "Fully qualified domain name")
	port := flag.String ("port", "443", "Port number")
	proxy_host := flag.String ("proxy-host", "", "Proxy host")
	proxy_port := flag.String ("proxy-port", "3128", "Proxy port number")

	flag.Parse()

	var success int

	if *proxy_host == "" {
		success = connect_to_host (*du_fqdn, *port)
	} else {
		success = connect_to_host_via_proxy (*proxy_host, *proxy_port, *du_fqdn, *port)
	}

	os.Exit (success)
}
