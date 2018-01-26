#!/bin/sh

# Used only by the deb installer. For the corresponding rpm actions, see pf9-muster.spec's %preun section.

service pf9-muster stop >/dev/null 2>&1
rm -rf /var/run/pf9-muster

