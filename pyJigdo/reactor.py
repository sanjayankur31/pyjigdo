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

from twisted.internet import reactor as treactor
from twisted.internet import defer, task
import twisted.web.client
from constants import PYJIGDO_USER_AGENT
import os, types

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

class PyJigdoReactor:
    """ The pyJigdo Reactor. Used for async operations. """

    def __init__(self, threads=1, timeout=10):
        """ Our main async gears for connecting to remote sites
            and downloading the data that we need. """
        self.reactor = treactor
        self.threads = threads
        self.timeout = timeout
        self.pending_actions = []

    def add_task(self, task_object):
        """ Add an object to the pending actions.
            This object must have a run(reactor) function we can
            call when the reactor is ready to run it. """
        self.pending_actions.append(task_object)

    def get_tasks(self):
        """ Get all of the pending tasks. """
        if not self.pending_actions: 
            self.finish()
        for t in self.pending_actions:
            yield t.run(self)
        self.clear_pending_actions()

    def checkpoint(self, ign):
        """ Check to see if we have anything to do. """
        pending_tasks = self.get_tasks()
        if pending_tasks:
            d = []
            c = task.Cooperator()
            for i in xrange(self.threads):
                dc = c.coiterate(pending_tasks)
                d.append(dc)
            dl = defer.DeferredList(d)
            dl.addCallback(self.checkpoint)
        else:
            print "Nothing pending, moving to finish. "
            self.finish()

    def run(self):
        """ Start the reactor, first checking to see if we have
            anything to do. """
        if self.pending_actions:
            self.checkpoint(None)
            self.reactor.run()
        else:
            pass # FIXME

    def finish(self):
        """ Check to see if we are done. If not, checkpoint().
            If so, stop the reactor. """
        if self.pending_actions:
            self.checkpoint(None)
        else:
            try:
                self.reactor.stop()
            except RuntimeError, e:
                pass

    def clear_pending_actions(self):
        """ Clear pening actions. """
        self.pending_actions = []

    def download_complete(self, r, url):
        """ The reactor reports a successful download. """
        print "complete"
        #print r, url

    def download_failure(self, e, url):
        """ The reactor reports something went wrong. """
        print  "failed"
        #print e, url

    def download_data(self, storage_location, remote_target):
        """ Try to download the data from remote_target to 
            given storage_location. """
        d = self.getFile(remote_target, storage_location,
                         agent=PYJIGDO_USER_AGENT, timeout=self.timeout)
        d.addCallback(self.download_complete, remote_target)
        d.addErrback(self.download_failure, remote_target)
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

    def init_jigdo_file(self, storage_location, remote_target):
        """ Fetch a jigdo file and parse it's data. """
        d = self.download_data(storage_location, remote_target)
        d.addCallback(self.parse_jigdo, storage_location)

    def parse_jigdo(self, storage_location):
        # FIXME, call the jigdo parser.
        # We should have a valid storage_location for this
        # data now.
        pass



