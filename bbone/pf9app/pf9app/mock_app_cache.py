# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'leb'

from pf9app.app_cache import AppCache
from urlparse import urlsplit

class MockAppCache(AppCache):

    def __init__(self, cachelocation):
        self.downloads = {}

    def download(self, name, version, url):
        key = (name, version)
        if key not in self.downloads:
            filename = urlsplit(url).path.split('/')[-1]
            self.downloads[key] = '/tmp/cache/%s/%s/%s' %\
                                  (name, version, filename)
        return self.downloads[key]



