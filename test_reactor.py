#!/usr/bin/python
# Test the reactor.

from pyJigdo.reactor import *

import os

class GetFile:
    def __init__(self, url, target_location):
        self.url = url
        self.target_location = target_location

    def run(self, reactor):
        """ Return what we want to do. """
        return reactor.download_data(self.target_location, self.url)

class GetJigdo(GetFile):
    def run(self, reactor):
        """ Call a jigdo init in the reactor. """
        return reactor.init_jigdo_file(self.target_location, self.url)

http_downloader = PyJigdoReactor()

urls = { "googlehome.html" : "http://google.com",
         "yahoohome.html" : "http://yahoo.com" }

for name, target in urls.iteritems():
    get_file = GetFile(target, os.path.join(os.getcwd(), name))
    http_downloader.add_task(get_file)

http_downloader.run()

