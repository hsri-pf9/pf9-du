# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved

import paste.deploy
import paste.httpserver
import os
import os.path

# FIXME - would be nice to be able to provide the pecan config file in the paste ini.
application = paste.deploy.loadapp('config:resmgr-paste.ini',
                  relative_to = os.getcwd(),
                  global_conf = {'config' : os.path.join(os.getcwd(), 'config.py')})

paste.httpserver.serve(application, port = 8083)
