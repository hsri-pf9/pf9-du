package cmd

import (
	"errors"
	"fmt"
	"net/url"
	"strconv"
	"strings"

	log "github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
)

const urlparseShortDescription string = "Parse a proxy url"
const urlparseLongDescription string = `The proxy url should have the format:
[<protocol>][<username>:<password>@]<proxy_host>:<proxy_port>`

const defaultPort int = 3128
const defaultProtocol string = "http://"

var urlparseCmd = &cobra.Command{
	Use:   "urlparse",
	Short: urlparseShortDescription,
	Long:  urlparseLongDescription,
	RunE:  urlparseRun,
}

func init() {
	RootCmd.AddCommand(urlparseCmd)
}

func urlparseRun(cmd *cobra.Command, args []string) error {
	if len(args) < 1 {
		return errors.New("URL was not specified")
	}
	if len(args) > 1 {
		return errors.New("Only URL argument must be specified")
	}
	rawUrl := args[0]
	if !strings.Contains(rawUrl, "://") {
		rawUrl = defaultProtocol + rawUrl
	}

	parsedUrl, err := url.Parse(rawUrl)
	if err != nil {
		return err
	}

	protocol := parsedUrl.Scheme
	if protocol != "http" && protocol != "https" {
		return errors.New("Invalid protocol: " + protocol)
	}

	user, pass, err := parseUserInfo(parsedUrl.User)
	if err != nil {
		return err
	}

	host, port, err := parseHostAndPort(parsedUrl.Host)
	if err != nil {
		return err
	}

	log.Debug("Protocol: ", protocol)
	log.Debug("Host: ", host)
	log.Debug("Port: ", port)
	log.Debug("User: ", user)
	log.Debug("Pass: ", pass)

	if user != "" && pass != "" {
		fmt.Println(protocol, host, port, user, pass)
	} else {
		fmt.Println(protocol, host, port)
	}

	return nil
}

func parseUserInfo(userInfo *url.Userinfo) (string, string, error) {
	if userInfo == nil {
		return "", "", nil
	}
	user := userInfo.Username()
	pass, hasPass := userInfo.Password()
	if !hasPass {
		return user, pass, errors.New("Password not found in user info: " + userInfo.String())
	}
	return user, pass, nil
}

func parseHostAndPort(address string) (string, int, error) {
	components := strings.Split(address, ":")
	if len(components) == 2 {
		host := components[0]
		portStr := components[1]
		port, err := strconv.Atoi(portStr)
		if err != nil {
			return host, port, errors.New("Could not parse port: " + err.Error())
		}
		return host, port, nil
	}
	if len(components) == 1 {
		host := components[0]
		return host, defaultPort, nil
	}
	return "", 0, errors.New("Unexpected address format (expected <host>:<port>): " + address)
}
