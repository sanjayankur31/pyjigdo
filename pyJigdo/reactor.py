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
        self.pending_actions = []
        self.pending_tasks = 0
        self.base = None # PyJigdoBase()

    def seed(self, base):
        """ Seed the reactor, assigning the PyJigdoBase() and
            then using data from this object to setup the first
            needed actions to kick everything off. """
        self.base = base
        self.log.debug(_("Seeding the reactor with requested jigdo resources."))
        for jigdo_file in self.base.jigdo_files.values():
            self.log.debug(_("Adding %s download task." % jigdo_file.id))
            self.add_task(jigdo_file.get())

    def add_task(self, task_object):
        """ Add an object to the pending actions.
            This object must have a run(reactor) function we can
            call when the reactor is ready to run it. """
        self.pending_actions.append(task_object)
        self.pending_tasks += 1

    def finish_task(self):
        """ Reduce pending_tasks by one. """
        self.pending_tasks -= 1
        self.checkpoint(None)

    def get_tasks(self):
        """ Get all of the pending tasks. """
        if self.pending_actions:
            for t in self.pending_actions:
                try:
                    yield t.run(self)
                except AttributeError:
                    pass
            self.clear_pending_actions()

    def checkpoint(self, ign, relax=False):
        """ Check to see if we have anything to do.
            Conditionally, sleep. """
        if relax:
            try:
                time.sleep(5)
            except KeyboardInterrupt:
                self.log.critical(_("Shutting down on user request!"))
                self.stop()
        if self.pending_actions:
            pending_tasks = self.get_tasks()
            d = []
            c = task.Cooperator()
            for i in xrange(self.threads):
                dc = c.coiterate(pending_tasks)
                d.append(dc)
            dl = defer.DeferredList(d)
            dl.addCallback(self.checkpoint)
        elif not self.pending_tasks > 0:
            self.finish()

    def run(self):
        """ Start the reactor, first checking to see if we have
            anything to do. """
        if self.pending_actions:
            self.checkpoint(None)
            self.reactor.run()
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
        if self.pending_actions:
            self.log.debug(_("Still pending items, checkpointing..."))
            self.checkpoint(None)
        elif self.pending_tasks > 0:
            self.log.debug(_("Still pending tasks, relaxed checkpointing..."))
            self.checkpoint(None, relax=True)
        else:
            self.stop()

    def clear_pending_actions(self):
        """ Clear pening actions. """
        self.pending_actions = []

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
        d = self.getFile( jigdo_object.source(),
                          jigdo_object.target(),
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

