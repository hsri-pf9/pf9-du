#!/bin/bash
# Copyright (c) 2016 Platform9 Systems Inc.

function ntpd_ask()
{
    read -p "Do you want to install and configure NTPD (yes/no)? " yn
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
