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

import os
import urlparse

import pyjigdo
import pyjigdo.image

import pyjigdo.translate as translate
from pyjigdo.translate import _, N_

class PyJigdoCLI:
    def __init__(self, base):
        # Remember base
        self.base = base
        # For abbreviatety
        self.cfg = base.cfg
        self.log = base.log

    def run(self):
        """Start the run"""

        # Load the .jigdo file
        self.base.load_jigdo(self.cfg.jigdo_url)

        # Select the images as per the command line
        if not self.base.select_images():
            self.select_images_interaction()

        self.download_images()

    def select_images_interaction(self):
        choosing_images = True
        # Require Raw Input
        while choosing_images:
            print "Please select one or more of the available Images:"
            for image in self.base.jigdo_definition.images['index']:
                print "#%d: %s" % (image,self.base.jigdo_definition.images['index'][image].filename)

            num_images = len(self.base.jigdo_definition.images['index'])
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
                    self.log.error(_("NAN!"), recoverable = True)
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

    def download_images(self):
        for image in self.base.jigdo_definition.images['index']:
            this_image = self.base.jigdo_definition.images['index'][image]
            if this_image.selected:
                print this_image.__dict__
                selected_image = pyjigdo.jigdo.JigdoTemplate(this_image.template_md5sum, this_image.template, self.cfg)
