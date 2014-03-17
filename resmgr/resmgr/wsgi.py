# Copyright (c) 2014 Platform9 Systems Inc.
# All Rights reserved

from pecan.deploy import deploy
from pecan.configuration import conf_from_file

# paste factory:
def app_factory(global_config, **local_conf):

    # override policy enforcement if paste config says so.
    config = conf_from_file(global_config['config'])
    enforce = local_conf.get('enforce_policy', 'true').lower() == 'true'
    config.update({'resmgr' : {'enforce_policy' : enforce}})

    return deploy(config.to_dict())


