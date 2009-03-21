#!/bin/env python
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

from optparse import OptionParser
import os, sys

# Add a hack to allow running from a git clone.
# This needs to be removed before any public release.
sys.path.append(os.getcwd())

import pyJigdo.base
from pyJigdo.constants import *

"""
pyJigdo interface - Jigdo at its finest
"""

import pyJigdo.translate as translate
from pyJigdo.translate import _, N_

class PyJigdo:
    """ The main interface to configuring pyJigdo.
        Providing runtime options and defaults for population
        of a PyJigdoBase() object that will further setup objects
        in preparation of creating a PyJigdoReactor() for downloading
        all of the requested data. """ 
    def __init__(self):
        """ Parse runtime options and setup the PyJigdoBase(). """
        self.parse_options()

        self.base = pyJigdo.base.PyJigdoBase(self)

    def parse_options(self):
        epilog = """pyJigdo is a Fedora Unity product. """ + \
                 """For more information about pyJigdo, visit http://pyjigdo.org/ """

        usage = "Usage: %prog [options] jigdofile [jigdofile]"

        try:
            parser = OptionParser( epilog = epilog,
                                   version = "%prog " + PYJIGDO_VERSION,
                                   usage = usage)
        except TypeError:
            parser = OptionParser()

        ##
        ## Generated Defaults
        ##
        default_base_path = os.getcwd()
        default_dest = default_base_path
        default_work = os.path.join(default_base_path, 'pyjigdo-data')
        default_logfile = os.path.join(default_base_path, 'pyjigdo.log')
        default_fallback = 5
        default_timeout = 15

        ##
        ## Runtime Options
        ##
        runtime_group = parser.add_option_group(_("Runtime Options"))
        runtime_group.add_option( "--list-images",
                                  dest    = "list_images",
                                  action  = "store_true",
                                  default = False,
                                  help    = _("List available images for given Jigdo files and exit."))

        ##
        ## Logging Options
        ##
        runtime_group.add_option( "-d", "--debug",
                                  dest    = "debug",
                                  action  = "store_true",
                                  default = False,
                                  help    = _("Set debugging to on."))
        runtime_group.add_option( "-v", "--verbose",
                                  dest    = "verbose",
                                  default = 0,
                                  type    = 'count',
                                  help    = _("Increase verbosity."))
        runtime_group.add_option( "--logfile",
                                  dest    = "logfile",
                                  action  = "store",
                                  default = default_logfile,
                                  help    = _("Logfile location. (Default: %s)" % default_logfile))

        ## Information Options
        general_group = parser.add_option_group(_("General Options"))
        general_group.add_option(   "--info",
                                    dest    = "jigdo_info",
                                    action  = "store_true",
                                    default = False,
                                    help    = _("Print information about the jigdo image and exit."))
        general_group.add_option(   "--fallback",
                                    dest    = "fallback_number",
                                    action  = "store",
                                    default = default_fallback,
                                    type    = 'int',
                                    help    = _("Number of public mirrors to try before using a fallback mirror. (Default: %s)" % default_fallback),
                                    metavar = _("[number of tries]"))
        general_group.add_option(   "-t", "--timeout",
                                    dest    = "download_timeout",
                                    action  = "store",
                                    default = default_timeout,
                                    type    = 'float',
                                    help    = _("Number of seconds to wait before switching to different slice source. (Default: %s)" % default_timeout),
                                    metavar = _("[number of seconds]"))

        ## Downloading Options
        ## Purpose: Allow a user to non-interactively download a defined image or images.
        ##          This should include being able to download all images with one command.
        ##          This is also for download options, like how many threads to use, to cache or not, etc.
        download_group = parser.add_option_group(_("Download Options"))
        download_group.add_option(  "-n", "--image-numbers",
                                    dest    = "image_numbers",
                                    default = [],
                                    action  = "append",
                                    type    = "str",
                                    help    = _("Download or Host a given comma-separated list of image number(s) or range(s). e.g.: \"7,15,23,8-13\""),
                                    metavar = _("[image numbers]"))
        download_group.add_option(  "-f", "--image-filenames",
                                    dest    = "image_filenames",
                                    default = [],
                                    action  = "append",
                                    type    = "str",
                                    help    = _("Download or Host a given comma-separated list of image filenames or file glob patterns. e.g.: \"*i386*CD*,foo.iso\""),
                                    metavar = _("[image filenames]"))
        download_group.add_option(  "-a", "--all",
                                    dest    = "image_all",
                                    action  = "store_true",
                                    default = False,
                                    help    = _("Download or Host all images defined in jigdo. Same as -f \"*\""))
        download_group.add_option(  "--threads",
                                    dest    = "download_threads",
                                    action  = "store",
                                    default = "2",
                                    help    = _("Number of threads to use when downloading."),
                                    metavar = _("[number]"))
        download_group.add_option(  "--download-storage",
                                    dest    = "download_storage",
                                    action  = "store",
                                    default = default_work,
                                    help    = _("Directory to store any temporary data for downloads."),
                                    metavar = _("[directory]"))

        # FIXME: We need to figure out a way to take a list of mirror sources to try for a given
        # Jigdo key (as defined in the jigdo) and add then as slice sources (and allow them to be
        # used exclusively/priority, as in the case of a local mirror.)
        
        # Possible solution is to use an append action option and ask for something like:
        # --local-mirror Updates-i386-key,http://ourserver/path/to/updates/
        # We would then inject all the members specified into our pool for slice data.

        #
        ## Scan Options
        ## Purpose: Allow a user to specify directories to scan for files, including pointing
        ## to existing ISO image(s)
        #
        scan_group = parser.add_option_group(_("Scan Options"))
        scan_group.add_option(      "-s", "--scan-dir",
                                    dest    = "scan_dirs",
                                    action  = "append",
                                    type    = "str",
                                    help    = _("Scan given directory for files needed by selected image(s)."),
                                    metavar = _("[directory]"))
        scan_group.add_option(      "--scan-iso",
                                    dest    = "scan_isos",
                                    action  = "append",
                                    type    = "str",
                                    help    = _("Mount and then scan existing ISO images for files needed by selected image(s)."),
                                    metavar = _("[iso image]"))

        # Parse Options, preserve the object for later use
        self.parser = parser
        (self.cli_options, self.jigdo_files) = parser.parse_args()

    def run(self):
        return self.base.run()

    def abort(self):
        """ Something has gone wrong. Try to shutdown and exit. """
        # FIXME: Add proper return codes and shutdown procedures for
        # the reactor and any other operations that might be running.
        return 1

    def done(self):
        """ Make sure we are done and then exit. """
        # FIXME: Add checks for any last minute things and exit.
        return 0

# If we are being run interactively,
# it's time to start up.
if __name__ == "__main__":
    pyJigdo_interface = PyJigdo()
    return_code = pyJigdo_interface.run()
    sys.exit(return_code)
