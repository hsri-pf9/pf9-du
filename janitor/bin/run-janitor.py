__author__ = 'Platform9'

from janitor.nova_cleanup import NovaCleanup
from ConfigParser import ConfigParser

if __name__ == "__main__":
    cfg = ConfigParser()
    cfg.read('/etc/pf9/janitor.conf')
    nv = NovaCleanup(cfg)
    nv.cleanup_hosts()
