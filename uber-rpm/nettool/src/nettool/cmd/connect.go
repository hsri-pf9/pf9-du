package cmd

import (
	"bufio"
	"crypto/tls"
	"encoding/base64"
	"errors"
	"fmt"
	"net"
	"strings"

	log "github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var connectShortDescription string = "Checks connectivity to a host"
var connectLongDescription string = `Checks connectivity to a host.
The connection can be made directly or through a proxy.`

var connectCmd = &cobra.Command{
	Use:   "connect",
	Short: connectShortDescription,
	Long:  connectLongDescription,
	RunE:  connectRun,
}

func init() {
	cobra.OnInitialize(initHostListConfig)

	RootCmd.AddCommand(connectCmd)

	connectCmd.Flags().StringP("host", "o", "localhost", "host to connect to")
	connectCmd.Flags().IntP("port", "p", 80, "port to connect to")
	connectCmd.Flags().StringP("proxy-protocol", "c", "http", "proxy protocol")
	connectCmd.Flags().StringP("proxy-host", "r", "", "proxy host")
	connectCmd.Flags().IntP("proxy-port", "t", 3128, "proxy port")
	connectCmd.Flags().StringP("proxy-user", "u", "", "proxy user")
	connectCmd.Flags().StringP("proxy-pass", "w", "", "proxy password")
}

func initHostListConfig() {
	viper.BindPFlag("host", connectCmd.Flags().Lookup("host"))
	viper.BindPFlag("port", connectCmd.Flags().Lookup("port"))
	viper.BindPFlag("proxy-protocol", connectCmd.Flags().Lookup("proxy-protocol"))
	viper.BindPFlag("proxy-host", connectCmd.Flags().Lookup("proxy-host"))
	viper.BindPFlag("proxy-port", connectCmd.Flags().Lookup("proxy-port"))
	viper.BindPFlag("proxy-user", connectCmd.Flags().Lookup("proxy-user"))
	viper.BindPFlag("proxy-pass", connectCmd.Flags().Lookup("proxy-pass"))
}

func connectRun(cmd *cobra.Command, args []string) error {
	host := viper.GetString("host")
	port := viper.GetInt("port")
	proxyProtocol := viper.GetString("proxy-protocol")
	proxyHost := viper.GetString("proxy-host")
	proxyPort := viper.GetInt("proxy-port")
	proxyUser := viper.GetString("proxy-user")
	proxyPass := viper.GetString("proxy-pass")

	if proxyHost == "" {
		return connect(host, port)
	} else {
		return connectViaProxy(host, port, proxyProtocol, proxyHost, proxyPort, proxyUser, proxyPass)
	}
}

func connectViaProxy(host string, port int, proxyProtocol string, proxyHost string,
	proxyPort int, proxyUser string, proxyPass string) error {
	log.Debug("Connecting via proxy")

	conn, err := dial(proxyProtocol, proxyHost, proxyPort)
	if err != nil {
		return err
	}
	_, err = sendConnectRequest(conn, host, port, proxyUser, proxyPass)
	if err != nil {
		return err
	}
	message, _ := bufio.NewReader(conn).ReadString('\n')
	conn.Close()
	if strings.Contains(strings.ToLower(message), "200 connection established") {
		return nil
	}
	return errors.New(fmt.Sprintf("Unexpected response from proxy: %s",
		strings.TrimSpace(message)))
}

func sendConnectRequest(conn net.Conn, host string, port int, proxyUser string,
	proxyPass string) (int, error) {
	text := fmt.Sprintf("CONNECT %s:%d HTTP/1.0\r\n", host, port)
	if proxyUser == "" || proxyPass == "" {
		text += "\r\n"
	} else {
		basic := base64.StdEncoding.EncodeToString(
			[]byte(fmt.Sprintf("%s:%s", proxyUser, proxyPass)))
		text += fmt.Sprintf("Proxy-Authorization: Basic %s\r\n\r\n", basic)
	}
	log.Debug("Sending CONNECT request:\n", text)
	return fmt.Fprintf(conn, text)
}

func dial(protocol string, host string, port int) (net.Conn, error) {
	address := fmt.Sprintf("%s:%d", host, port)
	log.Debug("Dialing address: ", address)
	log.Debug("Using proxy protocol: ", protocol)
	if protocol == "http" {
		return net.Dial("tcp", address)
	}
	if protocol == "https" {
		return tls.Dial("tcp", address, &tls.Config{
			InsecureSkipVerify: true,
		})
	}
	return nil, errors.New("Unexpected protocol: " + protocol)
}

func connect(host string, port int) error {
	log.Debug("Connecting directly")
	conn, err := dial("http", host, port)
	if err == nil {
		conn.Close()
	}
	return err
}
