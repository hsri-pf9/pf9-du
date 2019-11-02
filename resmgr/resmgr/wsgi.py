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


def version_factory(global_conf, **local_conf):
    config = conf_from_file(global_conf['config'])
    # Update the config to use a different controller. Potentially this can be
    # done in the pecan config as well. But this is good enough too.
    config.update({'app': {'modules': ['resmgr'], 'root': 'resmgr.controllers.root.VersionsController'}})
    return deploy(config.to_dict())
