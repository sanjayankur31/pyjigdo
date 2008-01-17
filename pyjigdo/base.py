#
# Copyright 2007, 2008 Fedora Unity
#
# Jonathan Steffan <jon a fedoraunity.org>
# Jeroen van Meeuwen <kanarip a fedoraunity.org>
# Ignacio Vazquez-Abrams <ivazqueznet+pyjigdo a gmail.com>
# Stewart Adam <s.adam a diffingo.com>

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

import logging
import sys

import pyjigdo.cfg
import pyjigdo.jigdo
import pyjigdo.logger

import pyjigdo.translate as translate
from pyjigdo.translate import _, N_

class PyJigdoBase:
    """PyJigdoBase holds common functions shared amongst our CLI and GUI mode"""
    def __init__(self, pyjigdo):
        """
        Initializes the PyJigdoBase class with the options specified from the command line.
        - Creates a logger instance
        - Creates a configuration store
        - Detects whether we are in CLI or GUI mode
        - Sets the logger configuration
        - Sets up the final configuration store
        """

        # Get the options parser, it's valuable ;-)
        self.parser = pyjigdo.parser

        # The options it has defined are valuable too
        self.cli_options = pyjigdo.cli_options

        # At this point, 'self' isn't much yet, so:
        # first create a simple logger instance that won't do much,
        # then create a configuration store with that logger,
        # then start detecting the mode that we are in (GUI / CLI),
        # then let the logger know about the configuration store,
        # then /really/ set up the configuration store (now that it has a
        #     valid logger that knows about the configuration store),
        #
        # Create logger
        self.create_logger()

        # Create ConfigStore (it needs the logger to be created!)
        self.create_configstore()

        # Detect our mode (options or try/except)
        self.detect_mode()

        # Let the logger know about cfg (it needs a ConfigStore instance!)
        self.log.set_config(self.cfg)

        # Then really setup the ConfigStore (because that needs a logger!)
        self.cfg.setup_cfg()

    def run(self):
        """Split into either running CLI, or GUI"""
        print "Running!!!"
        if self.cfg.cli_mode:
            import pyjigdo.cli
            self.log.debug(_("Running PyJigdo in CLI mode..."), level = 1)
            self.cli = pyjigdo.cli.PyJigdoCLI(self)
            try:
                self.cli.run()
            except KeyboardInterrupt:
                print ""
                print ""
                sys.exit(1)

        elif self.cfg.gui_mode:
            import pyjigdo.gui
            self.log.debug(_("Running PyJigdo in GUI mode..."), level = 1)
            self.gui = pyjigdo.gui.PyJigdoGUI(self)
            try:
                self.gui.run()
            except KeyboardInterrupt:
                print ""
                print ""
                sys.exit(1)

    def create_logger(self):
        """Create a logger instance using cli_options.debuglevel"""
        if not self.cli_options.debuglevel == None:
            loglevel = logging.DEBUG
        else:
            loglevel = logging.INFO
            self.cli_options.debuglevel = 0

        # Initialize logger
        self.log = pyjigdo.logger.Logger(loglevel = loglevel, debuglevel = self.cli_options.debuglevel)

    def create_configstore(self):
        """Initialize Configuration Store"""
        self.cfg = pyjigdo.cfg.ConfigStore(self)

    def detect_mode(self):
        """Detect whether we run in CLI or in GUI mode. (GUI is default)"""
        if self.cli_options.gui_mode:
            self.cfg._set_gui_mode()
        elif self.cli_options.cli_mode:
            self.cfg._set_cli_mode()
        else:
            try:
                import gtk
                import gtk.glade
                import gobject
                import gtk.gdk as gdk
                self.cfg._set_gui_mode()
            except:
                self.cfg._set_cli_mode()

    def load_jigdo(self, url):
        """Load a jigdo from a given URL using pyjigdo.misc.get_file"""
        self.log.debug(_("Loading Jigdo file %s") % url, level=2)
        file_name = pyjigdo.misc.get_file(url, self.cfg.working_directory)
        self.jigdo_definition = pyjigdo.jigdo.JigdoDefinition(file_name)

    def select_images(self):
        self.log.debug(_("Selecting Images"), level = 4)
        success = False
        if self.cfg.image_all:
            for image in self.jigdo_definition.images['index']:
                # Select Image
                self.select_image(image)

            return True
        elif self.cfg.image_numbers:
            print "%r" % self.cfg.image_numbers
            for image in self.cfg.image_numbers:
                if not self.select_image(image):
                    # Unable to select image
                    success = False
                    continue
            return success
        else:
            return False

    def select_image(self, image_unique_id):
        image_unique_id = int(image_unique_id)
        self.log.debug(_("Selecting Image %d") % image_unique_id, level = 4)
        success = True
        # Find the image with unique_id
        if self.jigdo_definition.images['index'].has_key(image_unique_id):
            self.jigdo_definition.images['index'][image_unique_id].selected = True
        else:
            self.log.warning(_("Could not select image %s") % image_unique_id)
            success = False

    def selected_images(self):
        images = []
        for image in self.jigdo_definition.images['index']:
            if self.jigdo_definition.images['index'][image].selected:
                images.append(str(image))
        return images