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
import pyJigdo.logger

import pyJigdo.translate as translate
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
        self.jigdo_templates = {} # {JigdoTemplate().id: JigdoTemplate(),}
        self.jigdo_slices = {} # {JigdoSlice().id: JigdoSlice(),}
        self.slice_sources = {} # {SliceSource().id: SliceSource(),}
        self.log = None # pyJigdoLogger()
        self.reactor = None # pyJigdoReactor()
        self.stats = None # pyJigdoStats()
        self.interface = None # pyJigdoTextInterface()
        self.scan_targets = [] # [pyJigdoScanTarget(),]

        # Set our exit points to callback.
        self.abort = pyjigdo_entry.abort
        self.done = pyjigdo_entry.done

        # Get the options parser, and bring it's options
        # and args into this namespace.
        self.parser = pyjigdo_entry.parser
        self.cli_options = pyjigdo_entry.cli_options
        self.args_jigdo_files = pyjigdo_entry.jigdo_files

        # Setup Logging.
        self.create_logger()

        # Prepare Jigdo
        self.prep_jigdo_files()

        # Start up the reactor
        self.run()

    def run(self):
        """ Start up the reactor and start performing operations to
            put the Jigdo together. """
        try:
            self.reactor = pyJigdo.reactor.pyJigdoReactor()
            self.reactor.seed(self)
            return self.reactor.run()
        except KeyboardInterrupt:
            print "\n\n"
        return self.abort()

    def create_logger(self):
        """ Create a logger instance setting an appropriate loglevel
            based on runtime options. """
        loglevel = pyJigdo.logger.CRITICAL
        if self.cli_options.verbose >= 3:
            loglevel = pyJigdo.logger.DEBUG
        elif self.cli_options.verbose = 2:
            loglevel = pyJigdo.logger.INFO
        elif self.cli_options.verbose = 1:
            loglevel = pyJigdo.logger.WARNING
        if self.cli_options.debug:
            loglevel = pyJigdo.logger.DEBUG

        # Initialize the logging object
        self.log = pyJigdo.logger.pyJigdoLogger( self.cli_options.log_file,
                                                 loglevel = loglevel )

    def prep_jigdo_files(self):
        """ Prepare selected Jigdo downloads for injection into our reactor. """
        for jigdo in self.args_jigdo_files:
            self.log.debug(_("Prepping Jigdo file %s ") % jigdo)
            self.jigdo_files[jigdo].append( pyJigdo.jigdo.JigdoFile(jigdo, self.log) )

