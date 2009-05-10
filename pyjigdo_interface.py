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

        description = "Python Interface to Jigdo."

        usage = "Usage: %prog [options] jigdofile [jigdofile]"

        try:
            parser = OptionParser( epilog = epilog,
                                   description = description,
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
        default_fallback = 3
        default_max_attempts = 6
        default_timeout = 30
        default_threads = 8
        default_jigdo_file_location = "/usr/bin/jigdo-file"

        ##
        ## Runtime Options
        ##
        runtime_group = parser.add_option_group(_("Runtime Options"))
        runtime_group.add_option( "--jigdo-file-bin",
                                  dest    = "jigdo_file_bin",
                                  action  = "store",
                                  default = default_jigdo_file_location,
                                  help    = _("Use given jigdo-file binary. (Default: %s)" % default_jigdo_file_location))
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
                                  action  = "count",
                                  default = 0,
                                  help    = _("Increase verbosity."))
        runtime_group.add_option( "--logfile",
                                  dest    = "log_file",
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
        general_group.add_option(   "--servers-only",
                                    dest    = "servers_only",
                                    action  = "store_true",
                                    default = False,
                                    help    = _("Don't use mirrorlists, if present. (Default: False)"))
        general_group.add_option(   "--max-attempts",
                                    dest    = "max_download_attempts",
                                    action  = "store",
                                    default = default_max_attempts,
                                    type    = 'int',
                                    help    = _("Max number of tries to get a file before giving up. (Default: %s)" % default_max_attempts),
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
                                    help    = _("Download a given comma-separated list of image number(s) or range(s). e.g.: \"7,15,23,8-13\""),
                                    metavar = _("[image numbers]"))
        download_group.add_option(  "-f", "--image-filenames",
                                    dest    = "image_filenames",
                                    default = [],
                                    action  = "append",
                                    type    = "str",
                                    help    = _("Download a given comma-separated list of image filenames or file glob patterns. e.g.: \"*i386*CD*,foo.iso\""),
                                    metavar = _("[image filenames]"))
        download_group.add_option(  "-a", "--all",
                                    dest    = "image_all",
                                    action  = "store_true",
                                    default = False,
                                    help    = _("Download all images defined in jigdo. Same as -f \"*\""))
        download_group.add_option(  "--threads",
                                    dest    = "download_threads",
                                    action  = "store",
                                    default = default_threads,
                                    help    = _("Number of threads to use when downloading. (Default: %s)" % default_threads),
                                    type    = "int",
                                    metavar = _("[number]"))
        download_group.add_option(  "--download-storage",
                                    dest    = "download_storage",
                                    action  = "store",
                                    default = default_work,
                                    help    = _("Directory to store any temporary data for downloads. (Default: %s)" % default_work),
                                    metavar = _("[directory]"))
        download_group.add_option(  "--download-target",
                                    dest    = "download_target",
                                    action  = "store",
                                    default = default_dest,
                                    help    = _("Directory to store final download data. (Default: %s)" % default_dest),
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

        if not self.check_options():
            self.show_help()
            print _("\nMissing required option!\n")
            sys.exit(1)

    def check_options(self):
        """ Check if we have the bare minimum needed options. """
        if not self.jigdo_files: return False
        # FIXME: Don't restrict to just one source
        # jigdo file. This is needed because we don't
        # have a lockable UI yet.
        if len(self.jigdo_files) > 1:
            print _("Sorry, multiple jigdo files are not supported yet.")
            print _("Soon we will support this!")
            print _("Given files were:")
            for f in self.jigdo_files:
                print "\t%s" % f
            if self.cli_options.image_filenames:
                self.shell_escape_help()
            sys.exit(1)
        return True

    def show_help(self):
        """ Show the help, with a logo. """
        print PYJIGDO_LOGO+"\n"
        self.parser.print_help()

    def shell_escape_help(self):
        """ Explain about shell escaping. """
        print _("\nYou have used -f and/or some sort of shell glob. (*)")
        print _("Your shell expanded that option and did not correctly pass")
        print _("it into pyjigdo. For example, if you selected all the DVD")
        print _("images with '-f *DVD*' you need to select them with the")
        print _("following:")
        print _("\t-f \*DVD\*\n")

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
    return_code = 0
    pyJigdo_interface = PyJigdo()
    pyJigdo_interface.base.run()
    if pyJigdo_interface.base.async.pending_downloads:
        pyJigdo_interface.base.async.checkpoint(None)
        try:
            return_code = pyJigdo_interface.base.async.reactor.run()
        except KeyboardInterrupt:
            print "\n\n"
            pyJigdo_interface.base.log.status(_("Exiting on user request.\n"))
            return_code = pyJigdo_interface.abort()
    else:
        pyJigdo_interface.base.log.critical(_("Reactor started with nothing to do!"))
    sys.exit(return_code)
