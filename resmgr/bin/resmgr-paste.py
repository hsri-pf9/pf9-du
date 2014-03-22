# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved

import paste.deploy
import paste.httpserver
import os
import os.path

# startup script for paste server testing

# FIXME - would be nice to be able to provide the pecan config file in the paste ini.
this_dir = os.path.abspath(os.path.dirname(__file__))
pecan_config = os.path.join(this_dir, '..', 'resmgr', 'tests', 'config.py')
paste_ini = os.path.join(this_dir, '..', 'resmgr', 'tests', 'resmgr-paste.ini')
application = paste.deploy.loadapp('config:%s' % paste_ini,
                                   global_conf = {'config' : pecan_config})

paste.httpserver.serve(application, port = 8083)
