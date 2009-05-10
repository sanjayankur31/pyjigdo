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

from twisted.internet import reactor
from twisted.internet import defer, task
from twisted.python import log
from twisted.web.client import *
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

class jigdoHTTPDownloader(HTTPDownloader):
    """Download to a file.
       This is a nasty hack to support download timeouts.
       This is supposed to be fixed in 9.x.

       This requires python-twisted-web-8.2.0! """

    # For the 8.2.0 packages: http://jsteffan.fedorapeople.org/SRPMS/
    # These will go into Fedora project ASAP.

    # We have commented this out because it's an overhead we don't
    # want to deal with right now. We will be getting pyjigdo running
    # with 8.2.0 and will then worry about supporting user-defined
    # timeout values.

    #def __init__(self, url, fileOrName,
    #             method='GET', postdata=None, headers=None,
    #             agent="Twisted client", supportPartial=0,
    #             timeout=0):
    #    self.requestedPartial = 0
    #    if isinstance(fileOrName, types.StringTypes):
    #        self.fileName = fileOrName
    #        self.file = None
    #        if supportPartial and os.path.exists(self.fileName):
    #            fileLength = os.path.getsize(self.fileName)
    #            if fileLength:
    #                self.requestedPartial = fileLength
    #                if headers == None:
    #                    headers = {}
    #                headers["range"] = "bytes=%d-" % fileLength
    #    else:
    #        self.file = fileOrName
    #    HTTPClientFactory.__init__(self, url, method=method, postdata=postdata,
    #                               headers=headers, agent=agent, timeout=timeout)
    #    self.deferred = defer.Deferred()
    #    self.waiting = 1

class PyJigdoReactor:
    """ The pyJigdo Reactor. Used for async operations. """

    def __init__(self, log, threads=1, timeout=10):
        """ Our main async gears for connecting to remote sites
            and downloading the data that we need. """
        self.log = log
        self.reactor = reactor
        self.threads = threads
        self.timeout = timeout
        self.pending_downloads = []
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
            if jigdo_file.has_data:
                self.log.info(_("A local file was given, not downloading %s" % jigdo_file.id))
                jigdo_file.download_callback_success(None)
            else:
                self.log.debug(_("Adding %s download task." % jigdo_file.id))
                jigdo_file.queue_download()

    def request_download(self, object):
        """ Add a request that the reactor download given object.
            Call object.get() to actually fetch the object. """
        self.pending_downloads.append(object)

    def parallel_get(self, objects, count, *args, **named):
        """ Run count number of objects.get() at a time. """
        coop = task.Cooperator()
        work = self.yield_work(objects)
        return defer.DeferredList([coop.coiterate(work) for i in xrange(count)])

    def yield_work(self, download_objects):
        """ Yield the work to be completed. """
        for download in download_objects:
            yield download.get()

    def checkpoint(self, ign):
        """ Check to see if we have anything to do. """
        self.log.debug(_("Pending Downloads: %s | Download Threads: %s" % \
                        ( len(self.pending_downloads),
                          self.base.settings.download_threads )))
        if self.pending_downloads:
            #downloads = self.get_pending_downloads(get_factor=1)
            downloads = self.get_pending_downloads()
            r = self.parallel_get( downloads,
                                   self.base.settings.download_threads )
            r.addCallback(self.checkpoint)
        else:
            self.finish()
        self.log.debug(_("Checkpoint exit."))

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
        else:
            self.stop()

    def get_pending_downloads(self, get_factor=0):
        """ Attempt to safely get a list of pending downloads. """
        r = []
        if get_factor:
            while self.pending_downloads and \
              not (len(r) >= (self.base.settings.download_threads * get_factor)):
                r.append(self.pending_downloads.pop(0))
        else:
            while self.pending_downloads:
                r.append(self.pending_downloads.pop(0))
        return r

    def download_object(self, jigdo_object):
        """ Try to download the data from jigdo_object.source()
            to jigdo_object.target() and call
            jigdo_object.download_callback_$status() when done. """
        target_location = jigdo_object.target()
        check_directory(self.log, os.path.dirname(target_location))
        d = downloadPage( jigdo_object.source(),
                          target_location,
                          agent = PYJIGDO_USER_AGENT )
        #                  timeout = self.timeout )
        d.addCallback(jigdo_object.download_callback_success)
        d.addErrback(jigdo_object.download_callback_failure)
        return d
