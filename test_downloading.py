#!/bin/env python
# Test the pyJigdo ASYNC download gears.
# This is a very basic test/example on downloading
# within the pyJigdo code.

from pyJigdo.logger import *
from pyJigdo.constants import *
from twisted.internet import reactor
from twisted.web.client import *

import os

class HTTP_Downloader:
    def __init__(self, log):
        self.log = log

    def download_data(self, remote_target, storage_location):
        """ Try to download the data from remote_target to 
            given storage_location. """
        d = downloadPage( remote_target, storage_location,
                          agent=PYJIGDO_USER_AGENT ) # , timeout=self.timeout)
        d.addCallback(self.download_complete, remote_target)
        d.addErrback(self.download_failure, remote_target)
        return d

    def download_complete(self, r, url):
        """ The reactor reports a successful download. """
        self.log.info("%s downloaded successfully.\n Extra Data: %s" % (url, r))

    def download_failure(self, e, url):
        """ The reactor reports something went wrong. """
        self.log.error("%s failed to download.\n Extra Data: %s" % (url, e))

class GetFile:
    def __init__(self, url, target_location):
        self.url = url
        self.target_location = target_location

    def get(self, r):
        """ Return what we want to do. """
        return r.download_data(self.url, self.target_location)

log = pyJigdoLogger("test_downloading.log", loglevel = logging.DEBUG)
http_downloader = HTTP_Downloader(log)

urls = { "fedoraunity.html" : "http://fedoraunity.org",
         "fedoraproject.html" : "http://fedoraproject.org" }

for name, target in urls.iteritems():
    get_file = GetFile(target, os.path.join(os.getcwd(), name))
    print "Requested downloading %s to %s" % \
          (target, os.path.join(os.getcwd(), name))
    get_file.get(http_downloader)

print "Ctrl-c to exit main loop."
reactor.run()

print "\nSucces!"

