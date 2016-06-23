#!/bin/bash
# Copyright (c) 2016 Platform9 Systems Inc.

function ntpd_ask()
{
    echo "Platform9 recommends using NTPD to keep the time in sync."
    read -p "Do you want to install and configure this now (yes/no)? " yn
    case $yn in
        [Yy]* ) install_ntpd; return 0;;
        [Nn]* ) print_ntpd_warning; return 0;;
        *) echo "Please answer yes or no."; exit 1;;
    esac
}

function print_ntpd_warning()
{
    echo "Warning: Skipping installation of NTPD"
    echo "Please ensure the time on this host is correct"
}
