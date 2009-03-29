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
from jigdo_file import execJigdoFile
from pyJigdo.util import check_directory
import os, types, time

import pyJigdo.translate as translate
from pyJigdo.translate import _, N_


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

    def __init__(self, log, threads=1, timeout=10):
        """ Our main async gears for connecting to remote sites
            and downloading the data that we need. """
        self.log = log
        self.reactor = treactor
        self.threads = threads
        self.timeout = timeout
        self.pending_downloads = []
        self.pending_tasks = 0
        self.base = None # PyJigdoBase()
        self.jigdo_file = None # execJigdoFile()

    def seed(self, base):
        """ Seed the reactor, assigning the PyJigdoBase() and
            then using data from this object to setup the first
            needed actions to kick everything off.

            Setup execJigdoFile().  """
        self.base = base
        self.jigdo_file = execJigdoFile( self.log,
                                         self.base.settings,
                                         self.base.settings.jigdo_file_bin )
        self.log.debug(_("Seeding the reactor with requested jigdo resources."))
        for jigdo_file in self.base.jigdo_files.values():
            self.log.debug(_("Adding %s download task." % jigdo_file.id))
            self.request_download(jigdo_file)

    def finish_task(self):
        """ Reduce pending_tasks by one and checkpoint
            if we are out of things to do. """
        self.pending_tasks -= 1
        if self.pending_tasks <= 0: self.checkpoint(None)

    def request_download(self, object):
        """ Add a request that the reactor download given object.
            Call object.get() to actually fetch the object. """
        self.pending_downloads.append(object)

    def parallel_get(self, objects, count, *args, **named):
        """ Run count number of objects.get() at a time. """
        coop = task.Cooperator()
        work = (download.get() for download in objects)
        self.pending_tasks += len(objects)
        d = defer.DeferredList([coop.coiterate(work) for i in xrange(count)])
        d.addCallback(self.checkpoint)
        return d

    def checkpoint(self, ign, relax=False):
        """ Check to see if we have anything to do.
            Conditionally, sleep. """
        if relax:
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                self.log.critical(_("Shutting down on user request!"))
                self.stop()
        if self.pending_downloads:
            downloads = self.get_pending_downloads()
            r = self.parallel_get( downloads,
                                   self.base.settings.download_threads )
        elif not self.pending_tasks > 0:
            self.finish()

    def run(self):
        """ Start the reactor, first checking to see if we have
            anything to do. """
        if self.pending_downloads:
            self.checkpoint(None)
            try:
                self.reactor.run()
            except KeyboardInterrupt:
                print "\n\n"
                self.log.status(_("Exiting on user request.\n"))
                return self.base.abort()
        else:
            self.log.critical(_("Reactor started with nothing to do!"))

    def stop(self):
        """ Stop the reactor. """
        try:
            self.reactor.stop()
        except RuntimeError, e:
            self.log.critical(_("Reactor reported: %s" % e))
        self.base.done()

    def finish(self):
        """ Check to see if we are done. If not, checkpoint().
            If so, attempt to stop() the reactor. It is possible
            there are still pending items, and if so checkpoint(). """
        self.log.debug(_("finish() has been called, checking for pending actions..."))
        if self.pending_downloads:
            self.log.debug(_("Still pending items, checkpointing..."))
            self.checkpoint(None)
        elif self.pending_tasks > 0:
            self.log.debug(_("Still pending tasks, relaxed checkpointing..."))
            self.checkpoint(None, relax=True)
        else:
            self.stop()

    def get_pending_downloads(self):
        """ Attempt to safely get a list of pending downloads. """
        r = []
        while self.pending_downloads:
            r.append(self.pending_downloads.pop(0))
        return r

    def download_complete(self, r, url):
        """ The reactor reports a successful download. """
        self.log.info(_("%s downloaded successfully." % url))

    def download_failure(self, e, url):
        """ The reactor reports something went wrong. """
        self.log.error(_("%s failed to download." % url))

    def download_object(self, jigdo_object):
        """ Try to download the data from jigdo_object.source()
            to jigdo_object.target() and call
            jigdo_object.download_callback() when done. """
        target_location = jigdo_object.target()
        check_directory(self.log, os.path.dirname(target_location))
        d = self.getFile( jigdo_object.source(),
                          target_location,
                          agent = PYJIGDO_USER_AGENT,
                          timeout = self.timeout )
        d.addCallback(jigdo_object.download_callback_success)
        d.addErrback(jigdo_object.download_callback_failure)
        return d

    def download_data(self, remote_target, storage_location):
        """ Try to download the data from remote_target to 
            given storage_location. """
        d = self.getFile(remote_target, storage_location,
                         agent=PYJIGDO_USER_AGENT, timeout=self.timeout)
        d.addCallback(self.download_complete, remote_target)
        d.addErrback(self.download_failure, remote_target)
        return d

    def getFile(self, url, file, contextFactory=None, *args, **kwargs):
        """Download an url to a file.
        @param file: path to file on filesystem, or file-like object.
        See jigdoHTTPDownloader to see what extra args can be passed.
        """
        self.log.debug(_("Attempting to download %s..." % url))
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

