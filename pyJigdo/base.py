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

import sys, os
from urlparse import urlparse
import pyJigdo.logger
import pyJigdo.pyasync
from pyJigdo.jigdo import JigdoFile

from pyJigdo.translate import _, N_

class PyJigdoBase:
    """ PyJigdoBase is the primary object that should be called back to.
        This object should be aware of all other objects and maintain their
        relationships and states. This class should be used to lookup all
        objects and their children. """
    def __init__(self, pyjigdo_entry):
        """ Initializes the PyJigdoBase class with the options specified
            from the command line. Setup all basic options and get things
            setup to start creating Jigdo objects. """

        self.jigdo_files = {} # {JigdoFile().id: JigdoFile(),}
        # FIXME: Populate these entry points.
        #self.jigdo_templates = {} # {JigdoTemplate().id: JigdoTemplate(),}
        #self.jigdo_slices = {} # {JigdoSlice().id: JigdoSlice(),}
        #self.slice_sources = {} # {SliceSource().id: SliceSource(),}
        # / FIXME
        self.log = None # PyJigdoLogger()
        self.async = None # PyJigdoReactor()
        self.stats = None # PyJigdoStats()
        self.interface = None # PyJigdoTextInterface()
        self.scan_targets = [] # [PyJigdoScanTarget(),]

        # Set our exit points to callback.
        self.abort = pyjigdo_entry.abort
        self.done = pyjigdo_entry.done

        # Get the options parser, and bring it's options
        # and args into this namespace.
        self.parser = pyjigdo_entry.parser
        self.settings = pyjigdo_entry.cli_options
        self.args_jigdo_files = pyjigdo_entry.jigdo_files

        # Setup Logging.
        self.create_logger()

    def run(self):
        """ Start up the reactor and start performing operations to
            put the Jigdo together. """
        # Setup Reactor
        self.async = pyJigdo.pyasync.PyJigdoReactor( self.log,
                     threads = self.settings.download_threads,
                     timeout = self.settings.download_timeout )
        # Prepare Jigdo
        if self.prep_jigdo_files():
            # Seed Reactor
            self.async.seed(self)
        else:
            self.log.critical(_("Seems there is nothing to do!"))
            return self.done()

    def create_logger(self):
        """ Create a logger instance setting an appropriate loglevel
            based on runtime options. """
        loglevel = pyJigdo.logger.CRITICAL
        if self.settings.verbose >= 3:
            loglevel = pyJigdo.logger.DEBUG
        elif self.settings.verbose == 2:
            loglevel = pyJigdo.logger.INFO
        elif self.settings.verbose == 1:
            loglevel = pyJigdo.logger.WARNING
        if self.settings.debug:
            loglevel = pyJigdo.logger.DEBUG

        # Initialize the logging object
        self.log = pyJigdo.logger.pyJigdoLogger( self.settings.log_file,
                                                 loglevel = loglevel )

    def prep_jigdo_files(self):
        """ Prepare selected Jigdo downloads for injection into our reactor. """
        for jigdo in self.args_jigdo_files:
            self.log.info(_("Prepping Jigdo file %s ") % jigdo)
            jigdo_url = urlparse(jigdo)
            jigdo_filename = os.path.basename(jigdo_url.path)
            if jigdo_url.scheme or \
               (not jigdo_url.scheme and os.path.isfile(jigdo_url.path)):
                jigdo_storage_location = os.path.join( self.settings.download_target,
                                                       jigdo_filename )
                self.log.debug(_("Adding Jigdo file %s" % jigdo_url.geturl()))
                self.log.debug(_("Storing Jigdo %s at %s" % ( jigdo_filename,
                                                              jigdo_storage_location )))
                self.jigdo_files[jigdo] = JigdoFile( self.log,
                                                     self.async,
                                                     self.settings,
                                                     self,
                                                     jigdo_url.geturl(),
                                                     jigdo_storage_location )
                if os.path.isfile(jigdo_url.path): self.jigdo_files[jigdo].has_data = True
            else:
                self.log.error(_("Jigdo file %s seems to not be valid." % jigdo))
                self.log.error(_("Cowardly refusing to use/download."))
        if not self.jigdo_files:
            self.log.critical(_("Nothing given to download!"))
            return False
        return True


