# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

from abc import ABCMeta, abstractmethod

class AppCache(object):
    """
    Models a download and cache manager for app packages.
    """
    __metaclass__ = ABCMeta

    @abstractmethod
    def download(self, name, version, url):
        """
        Downloads an application package if not in the cache.

        :return: the path of the locally downloaded package file
        :rtype: str
        """
        pass
