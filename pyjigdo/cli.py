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

import os, sys, urlparse, re

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

        # Report the results to the user
        self.report_results()

    def select_images_interaction(self):
        """ Interactively work with the user to select what images to download. """
        choosing_images = True
        num_images = len(self.base.jigdo_definition.images)
        image_maxwidth = len(str(num_images))   # for justified formatting
        # Require Raw Input
        while choosing_images:
            print "Please select one or more of the available Images:"
            for image in self.base.jigdo_definition.images:
                #print "#%d: %s" % (image,self.base.jigdo_definition.images[image].filename)
                print "%*s: %s" % (image_maxwidth+1, "#" + str(image), self.base.jigdo_definition.images[image].filename)

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
            
            # Then, split and expand ranges, if any
            image_choices = image_choice.split()
            expanded_image_choices = []
            for choice in image_choices:
                if '-' in choice:
                    range_start, range_end = choice.split('-')
                    try:
                        range_start = int(range_start)
                        range_end = int(range_end)
                        if range_start <= range_end:
                            step = 1
                        else:
                            step = -1
                        expanded_image_choices.extend(range(range_start, range_end + step, step))
                    except ValueError, e:
                        self.log.error(_("Invalid range selection."), recoverable = True)
                        continue
                else:
                    expanded_image_choices.append(choice)

            # Finally
            for choice in expanded_image_choices:
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
        pending_compose = False
        # Add images that need to be composed
        for (image_id, image) in self.base.jigdo_definition.images.iteritems():
            if image.selected:
                self.base.add_recompose(image)
                if not image.finished:
                    self.base.add_download_jobs(image)
                    pending_compose = True
        if not pending_compose:
            self.log.info(_("All images have reported as complete. Nothing to do."))
            return
        # Build a list of globally needed files, setup scan tasks
        self.base.setup_file_lookup()
        if self.cfg.scan_dirs:
            for directory in self.cfg.scan_dirs:
                self.base.add_scan_job(directory)
        if self.cfg.scan_isos:
            for iso in self.cfg.scan_isos:
                self.base.add_scan_job(iso, is_iso=True)

    def report_results(self):
        """ Tell the user what happened. """
        for (image_id, image) in self.base.jigdo_definition.images.iteritems():
            if image.selected:
                image.check_self()
                if image.finished:
                    self.log.info(_("Image %s successfully downloaded to: %s" %
                                    (image.filename,
                                    image.location)))
                else:
                    self.log.error(_("Image %s failed to complete. Try running pyjigdo again." %
                                     image.filename), recoverable=False)
