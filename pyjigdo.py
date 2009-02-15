#!/usr/bin/python
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

import pyjigdo.base
from pyjigdo.constants import *

"""
pyjigdo interface - Jigdo at its finest
"""

import pyjigdo.translate as translate
from pyjigdo.translate import _, N_

class PyJigdo(object):
    def __init__(self):
        # Create the command line options
        self.parse_options()

        self.base = pyjigdo.base.PyJigdoBase(self)

        # Answer questions
        self.answer_questions()

    def parse_options(self):
        epilog = """pyJigdo is a Fedora Unity product. For more information about pyJigdo, visit
                http://pyjigdo.org/"""

        try:
            parser = OptionParser(epilog=epilog, version="%prog " + VERSION)
        # FIXME: No bare excepts
        except:
            parser = OptionParser()

        ##
        ## Generated Defaults
        ##
        default_base_path = os.getcwd()
        default_dest = default_base_path
        default_work = os.path.join(default_base_path, 'pyjigdo-data')
        default_fallback = 5
        default_timeout = 15

        ##
        ## Runtime Options
        ##
        runtime_group = parser.add_option_group(_("Runtime Options"))
        runtime_group.add_option(   "--cli",
                                    dest    = "cli_mode",
                                    action  = "store_true",
                                    default = True,
                                    help    = _("Use the CLI rather than GUI (doesn't exist yet.)"))
        runtime_group.add_option(   "--list-images",
                                    dest    = "list_images",
                                    action  = "store_true",
                                    default = False,
                                    help    = _("List available images for a given Jigdo file."))

        ##
        ## Logging Options
        ##
        runtime_group.add_option(   "-d", "--debug",
                                    dest    = "debuglevel",
                                    default = 0,
                                    type    = 'int',
                                    help    = _("Set debugging level (0 by default)"))

        ##
        ## Configuration Options
        ##
        config_group = parser.add_option_group(_("Configuration Options"))
        config_group.add_option(    "-c", "--config",
                                    dest    = "config",
                                    action  = "store",
                                    default = os.path.join(BASE_CONF_DIR,"pyjigdo.conf"),
                                    help    = _("PyJigdo configuration file to use"),
                                    metavar = _("[config file]"))
        config_group.add_option(    "--dest-dir", "--destination-directory",
                                    dest    = "destination_directory",
                                    action  = "store",
                                    default = default_dest,
                                    help    = _("Destination directory for products. (Default: %s)" % default_dest),
                                    metavar = _("[directory]"))
        config_group.add_option(    "--work-dir", "--working-directory",
                                    dest    = "working_directory",
                                    action  = "store",
                                    default = default_work,
                                    help    = _("Working directory. (Default: %s)" % default_work),
                                    metavar = _("[directory]"))

        ## Information Options
        ## Purpose: We should allow a user to query a jigdo and get lots-o-info from just
        ##          downloading the jigdo file.
        general_group = parser.add_option_group(_("General Options"))
        general_group.add_option(   "-j", "--jigdo",
                                    dest    = "jigdo_url",
                                    action  = "store",
                                    default = "",
                                    help    = _("Location of jigdo file."),
                                    metavar = _("[url]"))
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
                                    dest    = "urlgrab_timeout",
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

        #
        ## Hosting Options
        ## Purpose: Allow a user to easily setup a location that contains all the needed
        ##          data defined in the jigdo. Preserve/create directory structure based
        ##          on defined [servers] path data.
        # FIXME: Status update: After the downloading engine is done, this will be the next
        #        priority for us.
        #
        #hosting_group = parser.add_option_group(_("Hosting Options (EXPERIMENTAL)"))
        #hosting_group.add_option(   "--host-image",
        #                            dest    = "host_image_numbers",
        #                            default = [],
        #                            action  = "append",
        #                            type    = "str",
        #                            help    = "Host given image number. (Not supported yet)",
        #                            metavar = "[image number]")
        #hosting_group.add_option(   "--host-all",
        #                            dest    = "host_all",
        #                            action  = "store_true",
        #                            default = False,
        #                            help    = "Host all images defined in jigdo.")
        #hosting_group.add_option(   "--host-data-dir",
        #                            dest    = "host_data_directory",
        #                            action  = "store",
        #                            default = "",
        #                            help    = "Directory to download data to.",
        #                            metavar = "[directory]")
        #hosting_group.add_option(   "--host-templates-dir",
        #                            dest    = "host_templates_directory",
        #                            action  = "store",
        #                            default = "",
        #                            help    = "Directory to download templates to.",
        #                            metavar = "[directory]")

        ##
        ### Generation Options
        ### Purpose: Allow a user to generate jigdo configs and templates.
        #generation_group = parser.add_option_group(_("Generation Options (EXPERIMENTAL)"))
        #generation_group.add_option("--iso-image",
                                    #dest    = "iso_image_locations",
                                    #default = [],
                                    #action  = "append",
                                    #type    = "str",
                                    #help    = "Build jigdo for given ISO image.",
                                    #metavar = "[image location]")
        ## FIXME: Any creative ways to take this data and not limit to just two repos?
        ## We need a way to be able to say "ISO 1 needs repo 1 and repo 2 found here and there with labels 1 and 2"
        ## What I've done here will require a command to pyjigdo per arch, kinda clunky
        #generation_group.add_option("--local-mirror-base",
                                    #dest    = "base_local_mirror",
                                    #action  = "store",
                                    #default = "",
                                    #help    = "Find base files from given local mirror.",
                                    #metavar = "[local location for base files]")
        #generation_group.add_option("--local-mirror-updates",
                                    #dest    = "updates_local_mirror",
                                    #action  = "store",
                                    #default = "",
                                    #help    = "Find updates files from given local mirror.",
                                    #metavar = "[local location for updates files]")
        #generation_group.add_option("--mirror-base-label",
                                    #dest    = "base_local_label",
                                    #action  = "store",
                                    #default = "Base",
                                    #help    = "Label for local mirror source 'base'. Default 'Base'",
                                    #metavar = "[label]")
        #generation_group.add_option("--mirror-updates-label",
                                    #dest    = "updates_local_label",
                                    #action  = "store",
                                    #default = "Updates",
                                    #help    = "Label for local mirror source 'updates'. Default 'Updates'",
                                    #metavar = "[label]")
        #generation_group.add_option("--generation-dir",
                                    #dest    = "generation_directory",
                                    #action  = "store",
                                    #default = "",
                                    #help    = "Directory to dump generated jigdo(s) into.",
                                    #metavar = "[directory]")
        #generation_group.add_option("--jigdo-name",
                                    #dest    = "jigdo_name",
                                    #action  = "store",
                                    #default = "pyjigdo-generated",
                                    #help    = "Name to give this jigdo. Result will be 'name'.jigdo",
                                    #metavar = "[name]")

        self.parser = parser
        # Parse Options
        (self.cli_options, self.args) = parser.parse_args()

        if not self.cli_options.jigdo_url:
            try:
                self.cli_options.jigdo_url = self.args[0]
            except IndexError:
                pass

        # No GUI, yet ;-) This time we are going to make the CLI very nice and bug free
        # and _then_ add a GUI.
        #if self.cli_options.gui_mode:
        #    print "No GUI, yet ;-) Running CLI..."
        #    self.cli_options.gui_mode = False

    def answer_questions(self):
        """Answers questions such as when --jigdo --info has been specified"""
        if self.cli_options.jigdo_info:
            sys.exit(pyjigdo.misc.jigdo_info(self.cli_options.jigdo_url,
                                             self.cli_options.working_directory,
                                             self.base.log,
                                             self.base.cfg))

        if self.cli_options.list_images:
            sys.exit(pyjigdo.misc.list_images(self.cli_options.jigdo_url,
                                              self.cli_options.working_directory,
                                              self.base.log,
                                              self.base.cfg))

    def run(self):
        return self.base.run()

# If we are being run interactively,
# it's time to start up.
if __name__ == "__main__":
    pyjigdo = PyJigdo()
    return_code = pyjigdo.run()
    sys.exit(return_code)
