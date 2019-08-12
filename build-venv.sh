#!/bin/bash

set -x

if [ -z "$2" ]; then
   virtualenv "$1"
else
   if  [ "$2" = "py3" ]; then
       virtualenv -p python3 "$1"
   else
       virtualenv "$1"
   fi
fi
