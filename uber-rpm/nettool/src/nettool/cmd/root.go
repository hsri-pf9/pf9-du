package cmd

import (
	"fmt"
	"os"

	log "github.com/sirupsen/logrus"
	"github.com/spf13/cobra"
	"github.com/spf13/viper"
)

var cfgFile string
var rootCmdName string = "nettool"
var rootShortDescription string = "PF9 Installer Utility"
var rootLongDescription string = `Runs utilities needed by the Platform9 installer

This includes checking network connectivity and parsing urls`

var RootCmd = &cobra.Command{
	Use:              rootCmdName,
	Short:            rootShortDescription,
	Long:             rootLongDescription,
	PersistentPreRun: rootPersistentPreRun,
	SilenceUsage:     true,
}

/* Main invocation to start the CLI */
func Execute() {
	if err := RootCmd.Execute(); err != nil {
		os.Exit(1)
	}
}

func init() {
	cobra.OnInitialize(initConfig)

	/* Subcommands inherit persistent flags */
	RootCmd.PersistentFlags().StringVar(&cfgFile, "config", "",
		"config file (default is $HOME/.nettool.yaml)")
	RootCmd.PersistentFlags().BoolP("debug", "d", false, "Enable debug logging")
}

func initConfig() {
	if cfgFile != "" { /* Use config flag if available */
		viper.SetConfigFile(cfgFile)
	}

	viper.SetConfigName(".nettool") // name of config file (without extension)
	viper.AddConfigPath("$HOME")    // adding home directory as first search path
	viper.AutomaticEnv()            // read in environment variables that match

	if err := viper.ReadInConfig(); err == nil {
		fmt.Println("Using config file:", viper.ConfigFileUsed())
	}
	viper.BindPFlag("debug", RootCmd.Flags().Lookup("debug"))
}

func rootPersistentPreRun(cmd *cobra.Command, args []string) {
	debug := viper.GetBool("debug")
	if debug {
		log.SetLevel(log.DebugLevel)
	}
}
