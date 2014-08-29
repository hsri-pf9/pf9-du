__author__ = 'Platform9'

from janitor import serve
import logging

logging.basicConfig(level=logging.DEBUG,
                    format='%(asctime)s %(name)-12s %(levelname)-8s %(message)s',
                    datefmt='%m-%d %H:%M')
serve('/etc/pf9/janitor.conf')
