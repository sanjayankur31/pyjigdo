#
# Copyright 2007-2009 Fedora Unity Project (http://fedoraunity.org)
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2, or (at your option) any
# later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

# Yes, this is just a teaser. I don't have code ready to transplant into
# pyJigdo... just example code that allows me to download objects. Hopefully
# next week we'll get to hacking out everything.

from twisted.internet import reactor as treactor
from twisted.internet import defer
import twisted.web.client
import os, types

test_http_agent = "pyJigdo Test Reactor/Twisted"
test_storage_location = os.getcwd()

# DISCLAIMER: This is example/placeholder code.

# FIXME: the jigdoHTTPDownloader is a super hack.
# This hack requires us to depend on a very specific version
# of twisted, which sucks. It might be worth the time to
# submit updates into Fedora for the latest twisted stuff
# but it *will* break other code that does something hacky
# such as this.

class jigdoHTTPDownloader(twisted.web.client.HTTPDownloader):
    """Download to a file.
       This is a nasty hack to support download timeouts.
       This is supposed to be fixed in 9.x. """

    def __init__(self, url, fileOrName,
                 method='GET', postdata=None, headers=None,
                 agent="Twisted client", supportPartial=0,
                 timeout=0):
        self.requestedPartial = 0
        if isinstance(fileOrName, types.StringTypes):
            self.fileName = fileOrName
            self.file = None
            if supportPartial and os.path.exists(self.fileName):
                fileLength = os.path.getsize(self.fileName)
                if fileLength:
                    self.requestedPartial = fileLength
                    if headers == None:
                        headers = {}
                    headers["range"] = "bytes=%d-" % fileLength
        else:
            self.file = fileOrName
        twisted.web.client.HTTPClientFactory.__init__(self, url, 
                           method=method, postdata=postdata,
                           headers=headers, agent=agent, timeout=timeout)
        self.deferred = defer.Deferred()
        self.waiting = 1

class ExampleSlice:
    """ An example slice object. """

    def __init__(self, name, remote_targets):
        self.urls = remote_targets
        # Base on user input/settings
        self.location = os.path.join(test_storage_location, name)

    def try_download(self, reactor):
        """ Inject ourself into the reactor with the needed callbacks. """
        target_url = self.get_pending_url()
        if target_url:
            job = reactor.downloadData(self.location, target_url)
            reactor.actions.append(job)
        else:
            # FIXME: Catch DownloadFailed() exception
            return False

    def get_pending_url(self):
        """ Get an url that we have not already tried.
            Return false if we have nothing. """
        try:
            return self.urls[0]
        except IndexError:
            # FIXME: Raise DownloadFailed() exception
            return False

    def verify(self):
        """ Verify we got the expected data. """
        return True

class PyJigdoReactor:
    """ The pyJigdo Reactor. Used for async operations. """

    def __init__(self, threads=1):
        self.reactor = treactor
        self.threads = threads
        self.actions = []
        self.objects = {}

    def addTask(self, task_object):
        """ Add an object to the pending tasks. """
        self.objects[task_object.location] = task_object
        task_object.try_download(self)

    def clearActions(self):
        """ Clear our actions list. """
        self.actions = []

    def generateTasks(self):
        """ Generate a deffered list to hand off to the reactor. """
        self.deferred = defer.DeferredList(self.actions, consumeErrors=1)
        self.deferred.addCallback(self.finish_run)
        self.clearActions()

    def checkpoint(self):
        """ Check that we don't have any more pending jobs,
            specifically outside of our reactor. """
        return False

    def finish_run(self, ign):
        # Verify objects are done and set status,
        # removing them as needed.
        for target, slice in self.objects.items():
            if slice.verify(): del self.objects[target]
        if not self.checkpoint(): self.reactor.stop()

    def downloadComplete(self, r, url):
        """ The reactor reports a successful download. """
        print "complete"
        #print r, url

    def downloadFailure(self, e, url):
        """ The reactor reports something went wrong. """
        print  "failed"
        #print e, url

    def downloadData(self, storage_location, remote_target):
        """ Try to download the data from remote_target to 
            given storage_location. """
        d = self.getFile(remote_target, storage_location,
                         agent=test_http_agent, timeout=10)
        d.addCallback(self.downloadComplete, remote_target)
        d.addErrback(self.downloadFailure, remote_target)
        return d

    def getFile(self, url, file, contextFactory=None, *args, **kwargs):
        """Download a web page to a file.
        @param file: path to file on filesystem, or file-like object.
        See jigdoHTTPDownloader to see what extra args can be passed.
        """
        scheme, host, port, path = twisted.web.client._parse(url)
        factory = jigdoHTTPDownloader(url, file, *args, **kwargs)
        if scheme == 'https':
            from twisted.internet import ssl
            if contextFactory is None:
                 contextFactory = ssl.ClientContextFactory()
            self.reactor.connectSSL(host, port, factory, contextFactory)
        else:
            self.reactor.connectTCP(host, port, factory)
        return factory.deferred


targets = {'google.homepage.html': ['http://www.google.com'],
           'yahoo.homepage.html':  ['http://yahoo.com']}

pyjigdo_downloader = PyJigdoReactor()

# Inject the test objects
for (name, remote_target) in targets.iteritems():
    jigdo_slice = ExampleSlice(name, remote_target)
    pyjigdo_downloader.addTask(jigdo_slice)

pyjigdo_downloader.generateTasks()
pyjigdo_downloader.reactor.run()

print "Done?!"

