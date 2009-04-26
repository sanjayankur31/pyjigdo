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

"""
User Interface
"""

import pyJigdo.util

import pyJigdo.translate as translate
from pyJigdo.translate import _, N_

class SelectImages:
    """ A class to work with the user to select what images
        they would like to download based on the Jigdo data
        we have already been able to acquire. """

    def __init__(self, log, settings, base, jigdo_definition):
        """ Interactively work with the user to select what images to download
            if there were not runtime options defining what to download.  """
        # FIXME (class wide): NO bare print()
        self.log = log
        self.settings = settings
        self.base = base
        self.jigdo_definition = jigdo_definition
        choosing_images = True
        num_images = len(self.jigdo_definition.images)
        image_maxwidth = len(str(num_images))

        if self.settings.image_numbers or self.settings.image_filenames or self.settings.image_all:
            self.select_images()
        else:
         while choosing_images:
            print "Please select one or more of the available Images:"
            for image in self.jigdo_definition.images:
                print "%*s: %s" % (image_maxwidth+1, "#" + str(image), self.jigdo_definition.images[image].filename)

            try:
                image_choice = raw_input("What image(s) would you like to download? [1-%s] " % num_images )
            except KeyboardInterrupt:
                self.base.abort()
            if image_choice == "":
                print "Choose the number(s) of the image file(s), seperated by commas or spaces, or specify a range (1-5)"
                continue
            try:
                ret = image_choice.index('all')
                choosing_images = False
                self.settings.image_all = True
                self.select_images()
                continue
            except ValueError, e:
                pass

            # convert "1,2  3-5, 8" to [1,2,3,4,5,8]
            expanded_image_choices = pyJigdo.util.image_numstr_to_list(image_choice)

            for choice in expanded_image_choices:
                try:
                    choice = int(choice)
                except ValueError, e:
                    self.log.error(_("Invalid selection."))
                    continue

                self.select_image(choice)

            print "Currently going to download image(s): %s" % ", ".join(self.selected_images())
            try:
                continue_selecting = raw_input("Would you like to select another image for download? [y/N] ")
            except KeyboardInterrupt:
                self.base.abort()
            if continue_selecting.lower() not in ["y", "yes"]:
                choosing_images = False

    def select_image(self, image_unique_id):
        """ Flip the switch to set an image to download.
            Return True if the action was successful. """
        image_unique_id = int(image_unique_id)
        self.log.debug(_("Selecting Image %d") % image_unique_id)
        success = False
        # Find the image with unique_id
        if self.jigdo_definition.images.has_key(image_unique_id):
            self.jigdo_definition.images[image_unique_id].select()
        else:
            self.log.warning(_("Could not select image %s") % image_unique_id)
            success = False
        return success

    def select_images(self):
        """ Select images based on selections by the user.
            Return True if actions were successful. """
        self.log.debug(_("Selecting Images"))
        success = False
        if self.settings.image_all or len(self.jigdo_definition.images) == 1:
            for image in self.jigdo_definition.images:
                # Select all Images
                self.select_image(image)
            success = True
        elif self.settings.image_numbers or self.settings.image_filenames:
            # Select images by number
            if self.settings.image_numbers:
                for image_numstr in self.settings.image_numbers:
                    for image in pyJigdo.util.image_numstr_to_list(image_numstr):
                        if self.select_image(image):
                            # At least one image was able to be selected,
                            # return successfully. We might want to make it more
                            # verbose if an image fails to select.
                            success = True
                        else:
                            self.log.warning(_("Could not select image %s") % image)
            # Select images by whole filename or glob pattern
            import re, fnmatch
            if self.settings.image_filenames:
                for image_filestr in self.settings.image_filenames:     # -f "*i386*,*ppc*" -f "file"
                    for image_file in image_filestr.replace(',',' ').split(): # [*i386*,*ppc*], [file]
                        regex = re.compile(fnmatch.translate(image_file))
                        for jignum, jigimg in self.jigdo_definition.images.iteritems():
                            #print jignum, jigimg.filename
                            if regex.match(jigimg.filename):
                                self.log.debug(_("%s MATCHED: %d: %s") % (image_file, jignum, jigimg.filename))
                                if self.select_image(jignum):
                                    success = True
                                else:
                                    self.log.warning(_("Could not select image %s") % image)
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


