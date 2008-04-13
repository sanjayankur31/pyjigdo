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

import os, sys, urlparse

import pyjigdo.translate as translate
from pyjigdo.translate import _, N_

class PyJigdoCLI:
    """ The pyJigdo Command Line Interface. """
    def __init__(self, base):
        # Populate our base CLI object
        # with information we can make good use of.
        self.base = base
        self.cfg = base.cfg
        self.log = base.log

    def run(self):
        """ Start the CLI and start working with what we have. """

        # Load the .jigdo file
        self.base.load_jigdo(self.cfg.jigdo_url)
        
        # Initialize the job pool
        self.base.create_job_pool()

        # Select the images as per the command line
        if not self.base.select_images():
            self.select_images_interaction()

        # Add the jobs we know we need to finish
        self.build_jobs()
        
        # Run everything
        self.base.run_tasks()

    def select_images_interaction(self):
        """ Interactively work with the user to select what images to download. """
        choosing_images = True
        # Require Raw Input
        while choosing_images:
            print "Please select one or more of the available Images:"
            for image in self.base.jigdo_definition.images:
                print "#%d: %s" % (image,self.base.jigdo_definition.images[image].filename)

            num_images = len(self.base.jigdo_definition.images)
            image_choice = raw_input("What image(s) would you like to download? [1-%s] " % num_images )
            if image_choice == "":
                print "Choose the number(s) of the image file(s), seperated by commas or spaces, or specify a range (1-5)"
                continue

            # Hey, if it says "all", we're good to go!
            try:
                ret = image_choice.index('all')
                choosing_images = False
                self.cfg.image_all = True
                self.base.select_images()
                continue
            except ValueError, e:
                pass

            # First, eliminate all the commas
            image_choice = image_choice.replace(',', ' ')
            # Then, eliminate all the double spaces
            try:
                while image_choice.index('  '):
                    image_choice = image_choice.replace('  ', ' ')
            except ValueError, e:
                    pass

            # FIXME: Then, see if there is a range in there somewhere
            # Not Implemented Yet

            # Finally
            image_choices = image_choice.split(' ')
            for choice in image_choices:
                try:
                    choice = int(choice)
                except ValueError, e:
                    self.log.error(_("Invalid selection."), recoverable = True)
                    continue

                self.base.select_image(choice)

            print "Currently going to download image(s): %s" % ", ".join(self.base.selected_images())
            continue_selecting = raw_input("Would you like to select another image for download? [y/N] ")
            if continue_selecting.lower() not in ["y", "yes"]:
                choosing_images = False
        if len(self.base.selected_images()) < 1:
            # FIXME: Don't be so brutal, let the user try again from this point.
            print "You must select an image to download. Exiting."
            sys.exit(1)

    def build_jobs(self):
        """ Create the jobs that are needed to complete the requested actions. """
        # Add images that need to be composed
        for (image_id, image) in self.base.jigdo_definition.images.iteritems():
            if image.selected:
                self.base.add_recompose(image)
                self.base.add_download_jobs(image)
        # Build a list of globally needed files, setup scan tasks
        self.base.setup_file_lookup()
        if self.cfg.scan_dirs:
            for directory in self.cfg.scan_dirs:
                self.base.add_scan_job(directory)
