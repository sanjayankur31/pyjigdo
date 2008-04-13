#
# Copyright 2007, 2008 Fedora Unity Project (http://fedoraunity.org)
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

import logging, sys, os
from urllib import unquote

import pyjigdo.cfg
import pyjigdo.jigdo
import pyjigdo.logger
from pyjigdo.jigdo import JigdoJobPool

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
        
        # Store our JigdoScanTarget objects so we can unmount() them
        self.scan_targets = []


    def run(self):
        """ Split into either running CLI, or GUI. """
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
        """ Create a logger instance using cli_options.debuglevel """
        if not self.cli_options.debuglevel == None:
            loglevel = logging.DEBUG
        else:
            loglevel = logging.INFO
            self.cli_options.debuglevel = 0

        # Initialize logger
        self.log = pyjigdo.logger.Logger(loglevel = loglevel, debuglevel = self.cli_options.debuglevel)

    def create_configstore(self):
        """ Initialize Configuration Store. """
        self.cfg = pyjigdo.cfg.ConfigStore(self)

    def detect_mode(self):
        """ Detect whether we run in CLI or in GUI mode. (GUI is default) """
        if self.cli_options.gui_mode:
            self.cfg._set_gui_mode()
        elif self.cli_options.cli_mode:
            self.cfg._set_cli_mode()
        else:

##
## FIXME: GUI is disabled
##
#            try:
#                import gtk
#                import gtk.glade
#                import gobject
#                import gtk.gdk as gdk
#                self.cfg._set_gui_mode()
#            except:
            self.cfg._set_cli_mode()

    def load_jigdo(self, url):
        """ Load a jigdo from a given URL using pyjigdo.misc.get_file. """
        self.log.debug(_("Loading Jigdo file %s") % url, level=2)
        file_name = pyjigdo.misc.get_file(url, working_directory = self.cfg.destination_directory, log = self.log)
        self.jigdo_definition = pyjigdo.jigdo.JigdoDefinition(file_name, self.log, self.cfg)
    
    def create_job_pool(self):
        """ Create the job pool. """
        self.queue = JigdoJobPool(self.log, self.cfg, self.jigdo_definition)
    
    def setup_file_lookup(self):
        """ Create a location where we can query globally needed files
            when doing pre-download data acquisition. """
        self.needed_files = {}
        for (image_id, image) in self.jigdo_definition.images.iteritems():
            if image.selected:
                for (slice_md5, slice) in image.slices.iteritems():
                    filename = unquote(slice.file_name)
                    self.needed_files[os.path.basename(filename)] = slice

    def select_images(self):
        """ Select images based on selections by the user.
            Return True if actions were successful. """
        self.log.debug(_("Selecting Images"), level = 4)
        success = False
        if self.cfg.image_all:
            for image in self.jigdo_definition.images:
                # Select all Images
                self.select_image(image)
            success = True
        elif self.cfg.image_numbers:
            for image in self.cfg.image_numbers:
                if self.select_image(image):
                    # At least one image was able to be selected,
                    # return successfully. We might want to make it more
                    # verbose if an image fails to select.
                    success = True
                else:
                    self.log.warning(_("Could not select image %s") % image)
        return success

    def progress_bar(self, title = "", parent = None, xml = None, callback = False):
        """This function should be used to determine the type of progress bar we need.
        There's three types:
            - GUI Dialog Progress Bar (separate dialog, window pops up)
            - GUI Nested Progress Bar (no separate dialog, progress bar is in gui.frame_xml)
            - CLI Progress Bar

        This function also determines whether we should have a Callback Progress Bar"""

        self.log.debug(_("Initting progress bar for ") + title, level = 9)

        if self.cfg.gui_mode:
            if callback:
                if not self.gui.frame_xml.get_widget("part_progress") == None:
                    return pyjigdo.progress.ProgressCallbackGUI(title = title, parent = self.gui, xml = self.gui.frame_xml)
                elif not self.gui.main_window == None:
                    return pyjigdo.progress.ProgressCallbackGUI(title = title, parent = self.gui, xml = self.gui.frame_xml)
                else:
                    return pyjigdo.progress.ProgressCallbackGUI(title = title, parent = parent, xml = xml)
            else:
                if not self.gui.frame_xml.get_widget("part_progress") == None:
                    return revisor.progress.ProgressGUI(title = title, parent = self.gui, xml = self.gui.frame_xml)
                elif not self.gui.main_window == None:
                    return pyjigdo.progress.ProgressGUI(title = title, parent = self.gui, xml = xml)
                else:
                    return pyjigdo.progress.ProgressGUI(title = title, parent = parent, xml = xml)
        else:
            if callback:
                return pyjigdo.progress.ProgressCallbackCLI(title = title)
            else:
                return pyjigdo.progress.ProgressCLI(title = title)

    def select_image(self, image_unique_id):
        """ Flip the switch to set an image to download. 
            Return True if the action was successful. """
        image_unique_id = int(image_unique_id)
        self.log.debug(_("Selecting Image %d") % image_unique_id, level = 4)
        success = True
        # Find the image with unique_id
        if self.jigdo_definition.images.has_key(image_unique_id):
            self.jigdo_definition.images[image_unique_id].select()
        else:
            self.log.warning(_("Could not select image %s") % image_unique_id)
            success = False
        return success

    def selected_images(self, fullObjects=False):
        """ Return a list of selected images. """
        images = []
        for image in self.jigdo_definition.images:
            if self.jigdo_definition.images[image].selected:
                if fullObjects:
                    images.append(self.jigdo_definition.images[image])
                else:
                    images.append(str(image))
        return images

    def add_recompose(self, image):
        """ Add the template to be assembled. Generate the needed slice objects. """
        self.log.debug(_("Adding image %s to our queue.") % image.template, level = 4)
        image.get_template(self.cfg.working_directory)
        image.collect_slices(self.jigdo_definition, self.cfg.working_directory)
    
    def add_download_jobs(self, image):
        """ Add the download jobs that need to be done for the given image. """
        self.log.debug(_("Creating download tasks for %s") % image.filename)
        for (slice_hash, slice_object) in image.slices.iteritems():
            self.queue.add_job('download', slice_object)
    
    def add_scan_job(self, location, is_iso=False):
        """ Add a scan job to source local data. """
        self.log.debug(_("Adding source %s to be scanned for data." % location), level=3)
        scan_object = False
        if is_iso:
            scan_object = pyjigdo.jigdo.JigdoScanTarget(location,
                                                        self.cfg,
                                                        self.log,
                                                        self.needed_files,
                                                        is_iso=is_iso)
        else:
            scan_object = pyjigdo.jigdo.JigdoScanTarget(location, self.log, self.needed_files)
        if scan_object:
            self.scan_targets.append(scan_object)
            self.queue.add_job('scan', scan_object)

    def run_tasks(self):
        """ Actually start dealing with selected images. It's go time. """
        while self.queue.jobs['scan']:
            self.queue.do_scan()
        
        while self.queue.jobs['download']:
            self.queue.do_compose()
            self.queue.do_download()

        if self.queue.finish_pending_jobs():
            self.log.info(_("Success!"))
        else:
            # FIXME: Don't exit, do something.
            self.log.info(_("Something is still to be done!"))
            self.queue.do_download_failures(report=True)
        
        # Cleanup Mounts, if any
        for scan_target in self.scan_targets:
            scan_target.unmount()
            
                
        
        
        
        
