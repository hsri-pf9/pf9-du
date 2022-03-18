#!/bin/bash

set -x

if [ -z "$2" ]; then
   virtualenv "$1"
else
   if  [ "$2" = "py3" ]; then
       python3 -m venv --copies "$1"
   else
       virtualenv "$1"
   fi
fi
