# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import contextlib
import logging
import os
from urlparse import urlsplit
from pf9app.app_cache import AppCache
from pf9app.exceptions import DownloadFailed
import requests
import platform

DOWNLOAD_CHUNK_SIZE = 512 * 1024

SUPPORTED_DEBIAN_DISTROS = set(['debian', 'ubuntu'])
SUPPORTED_REDHAT_DISTROS = set(['redhat', 'centos'])

def get_supported_distro(log=None):
    """
    Returns 'redhat' or 'debian' depending on the supported distro detected.
    If no supported distro can be detected, returns 'redhat' and logs the error.
    """
    dist_name = platform.linux_distribution()[0].lower()
    if dist_name in SUPPORTED_DEBIAN_DISTROS:
        return 'debian'
    else:
        if log and (dist_name not in SUPPORTED_REDHAT_DISTROS):
            log.warn("Could not detect OS distro. Defaulting to Red Hat Linux.")
        return 'redhat'

class Pf9AppCache(AppCache):
    """Class that implements the AppCache interface"""

    def __init__(self, cachelocation,
                 certfile=None, keyfile=None, ca_certs=False,
                 cert_reqs=None,
                 log=logging):
        """
        Constructs a package downloader and caching object.

        :param str cachelocation: Root directory for cache
        :param str certfile: Client certificate for SSL
        :param str keyfile: Client private key file for SSL
        :param str ca_certs: Certificates file for verifying server identity
        :param int cert_reqs: Whether server verification is required (not used)
        """
        # TODO: Maintaining the cache in a dict. Need to figure out how this will
        # persist across restarts of the backbone service
        self.downloads = {}
        self.cache_location = cachelocation
        self.log = log
        self.certfile = certfile
        self.keyfile = keyfile
        self.ca_certs = ca_certs

    def _download_file(self, srcurl, destfile):
        """
        Utility method to download contents from the provided URL to a local file
        :param str srcurl: URL of the source to get content from
        :param str destfile: Local file to be which the content is to be written. It
        will override previous contents, if the file already exists.
        :raises DownloadFailed: when downloading the file fails
        """
        self.log.info("Downloading file %s to %s", srcurl, destfile)
        if get_supported_distro(self.log) == "debian":
            srcurl = "".join(os.path.splitext(srcurl)[:-1]) + ".deb"
            destfile = "".join(os.path.splitext(destfile)[:-1]) + ".deb"

        try:
            with contextlib.closing(requests.get(srcurl,
                                                 verify=self.ca_certs,
                                                 cert=(self.certfile,
                                                       self.keyfile),
                                                 stream=True)) as response:
                # Raise HTTPError if status is not 200
                response.raise_for_status()
                with open(destfile, "w") as wf:
                    # Source files (rpms) could be huge,download them in chunks
                    for chunk in response.iter_content(DOWNLOAD_CHUNK_SIZE):
                        wf.write(chunk)
        except requests.exceptions.RequestException as e:
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
            if get_supported_distro(self.log) == "debian":
                localdest = "".join(os.path.splitext(localdest)[:-1]) + ".deb"

            self.downloads[key] = localdest

        self.log.debug("App cache state: %s", str(self.downloads))
        return self.downloads[key]
