# Copyright 2014 Platform9 Systems Inc.
# All Rights Reserved.

__author__ = 'Platform9'

import contextlib
import logging
import os
from six.moves.urllib.parse import urlparse
from urlparse import urlsplit
from pf9app.app_cache import AppCache
from pf9app.exceptions import DownloadFailed
import requests
import platform

DOWNLOAD_CHUNK_SIZE = 512 * 1024

SUPPORTED_DEBIAN_DISTROS = set(['debian', 'ubuntu'])
SUPPORTED_REDHAT_DISTROS = set(['redhat', 'centos',
                                'centos linux', 'scientific linux'])

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

    def _file_sizes_match(self, path, expected_size):
        """
        Checks if the file is of expected size. Returns False if it is not.
        Returns True otherwise.
        :param str path: Path to the file
        :param str expected_size: Expected file size
        """
        file_size = str(os.stat(path).st_size)
        if file_size != expected_size:
            self.log.error("Expected file %s to be of size %s, but size was %s",
                           path, expected_size, file_size)
            return False

        return True

    def _download_file(self, srcurl, destfile):
        """
        Utility method to download contents from the provided URL to a local file
        :param str srcurl: URL of the source to get content from
        :param str destfile: Local file to be which the content is to be written. It
        will override previous contents, if the file already exists.
        :raises DownloadFailed: when downloading the file fails
        """
        self.log.info("Downloading file %s to %s", srcurl, destfile)
        originaldir, originalfilename = os.path.split(os.path.abspath(destfile))
        tmp_file_name = originalfilename + ".incomplete"
        self.log.info("Writing to the .incomplete file %s. "
                      "This will be renamed back to original "
                      "file once the download is successfully complete " % (tmp_file_name))
        #create a .incomplete file to write the contents. This will be renamed
        #to original file once the download is successfully complete
        tmpdst = os.path.join(originaldir, tmp_file_name)
        content_length = None
        try:
            with contextlib.closing(requests.get(srcurl,
                                                 verify=self.ca_certs,
                                                 cert=(self.certfile,
                                                       self.keyfile),
                                                 stream=True)) as response:
                # Raise HTTPError if status is not 200
                response.raise_for_status()
                content_length = response.headers.get('content-length', None)
                if content_length is None:
                    msg = 'Could not determine the size of the file being downloaded.'
                    self.log.error(msg)
                    raise DownloadFailed(msg)
                with open(tmpdst, "wb") as wf:
                    # Python3: Cannot write bytes without opening the file in wb mode.
                    # Source files (rpms) could be huge,download them in chunks
                    for chunk in response.iter_content(DOWNLOAD_CHUNK_SIZE):
                        wf.write(chunk)
        except requests.exceptions.RequestException as e:
            self.log.error("Downloading %s failed: %s", srcurl, e)
            raise DownloadFailed(str(e))

        if not self._file_sizes_match(tmpdst, content_length):
            raise DownloadFailed("Downloaded file doesn't match expected size.")
        #rename the .incomplete file
        self.log.info("Renaming %s to %s" % (tmp_file_name, originalfilename))
        os.rename(tmpdst, destfile)
        self.log.info("Downloaded file %s to %s", srcurl, destfile)


    def download(self, name, version, url, change_extension):
        """
        Downloads an application package if not in the cache.

        :param str name: Name of the app
        :param str version: Version of the app
        :param str url: Url to download it from, if not in the cache
        :param bool change_extension: Change the url extension to .deb
                                      if a Debian OS is detected
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
            self.log.info("Downloading %s.%s", name, version)

            if change_extension and get_supported_distro(self.log) == "debian":
                url = "".join(os.path.splitext(url)[:-1]) + ".deb"
                localdest = "".join(os.path.splitext(localdest)[:-1]) + ".deb"

            self._download_file(url, localdest)
            self.downloads[key] = localdest

        self.log.debug("App cache state: %s", str(self.downloads))
        return self.downloads[key]
