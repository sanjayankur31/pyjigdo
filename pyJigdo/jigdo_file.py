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
jigdo-file calls and functions. These need to be implemented directly, without
shelling out for this information. For now, we just shell out to jigdo-file.
"""

import os
from pyJigdo.util import check_directory, run_command

import pyJigdo.translate as translate
from pyJigdo.translate import _, N_


class execJigdoFile:
    """ A class to shell out to jigdo-file and return
        data from commands. """
    def __init__(self, log, settings, jigdo_file):
        """ Use given jigdo-file to perform operations. """
        self.log = log
        self.settings = settings
        self.jigdo_file = jigdo_file
        self.jigdo_env = {'PATH': os.getenv('PATH')}

    def get_template_data(self, template_file):
        """ Return the template data from the given template_file. """
        # TODO: Return an object, not just the output.
        return run_command( self.log,
                            self.settings,
                            ["jigdo-file", "ls", "--template", template_file],
                            env=self.jigdo_env,
                            inshell=True )

    def stuff_bits_into_image(self, jigdo_image, file, destroy=False):
        """ Put given file into given jigdo_image.
            If destroy, the bits will be removed after being added to the
            target image. """
        self.log.debug(_("Stuffing %s into %s ..." % \
                        ( file, os.path.basename(jigdo_image.location) )))
        stuff_command = [ "jigdo-file", "make-image",
                          "--image", jigdo_image.location,
                          "--template", jigdo_image.fs_location,
                          "--jigdo", jigdo_image.jigdo_definition.file_name,
                          "-r", "quiet",
                          "--force",
                          file ]
        run_command( self.log,
                     self.settings,
                     stuff_command,
                     env=self.jigdo_env,
                     inshell=True )
        if destroy: os.remove(file)


