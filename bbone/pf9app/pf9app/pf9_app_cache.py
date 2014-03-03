# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import contextlib
import logging
import os
import urllib2
from urlparse import urlsplit

from pf9app.app_cache import AppCache
from pf9app.exceptions import DownloadFailed


DOWNLOAD_CHUNK_SIZE = 512 * 1024

class Pf9AppCache(AppCache):
    """Class that implements the AppCache interface"""

    def __init__(self, cachelocation, log = logging):
        # TODO: Maintaining the cache in a dict. Need to figure out how this will
        # persist across restarts of the backbone service
        self.downloads = {}
        self.cache_location = cachelocation
        self.log = log

    def _download_file(self, srcurl, destfile):
        """
        Utility method to download contents from the provided URL to a local file
        :param str srcurl: URL of the source to get content from
        :param str destfile: Local file to be which the content is to be written. It
        will override previous contents, if the file already exists.
        :raises DownloadFailed: when downloading the file fails
        """
        self.log.info("Downloading file %s to %s", srcurl, destfile)
        try:
            with contextlib.closing(urllib2.urlopen(srcurl)) as urlreq:
                with open(destfile, "w") as wf:
                    # Source files (rpms) could be huge,download them in chunks
                    while True:
                        data = urlreq.read(DOWNLOAD_CHUNK_SIZE)
                        if not data:
                            break
                        wf.write(data)
        except urllib2.URLError, e:
            self.log.error("Downloading %s failed: %s", srcurl, e)
            raise DownloadFailed(str(e))

        self.log.info("Downloaded file %s to %s", srcurl, destfile)


    def download(self, name, version, url):
        """
        Downloads an application package if not in the cache.

        :param str name: Name of the app
        :param str version: Version of the app
        :param str url: Url to download it from, if not in the cache
        :return: the path of the locally downloaded package file
        :rtype: str
        :raises DownloadFailed: when downloading the file fails
        """
        key = (name, version)
        if key not in self.downloads:
            filename = urlsplit(url).path.split('/')[-1]
            localdir = os.path.join(self.cache_location, name, version)
            # If dir path doesn't exist, then create it
            if not os.path.exists(localdir):
                os.makedirs(localdir)
            localdest = os.path.join(localdir, filename)
            self.log.info("Downloading %s.%s from %s to %s",
                          name, version, url, localdest)
            self._download_file(url, localdest)
            self.downloads[key] = localdest

        self.log.debug("App cache state: %s", str(self.downloads))
        return self.downloads[key]
