#!/usr/bin/python
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

        # Run
        self.run()

    def parse_options(self):
        epilog = """pyJigdo is a Fedora Unity product. For more information about pyJigdo, visit
                http://pyjigdo.org/"""

        try:
            parser = OptionParser(epilog=epilog)
        except:
            parser = OptionParser()

        ##
        ## Runtime Options
        ##
        runtime_group = parser.add_option_group(_("Runtime Options"))
        runtime_group.add_option(   "--cli",
                                    dest    = "cli_mode",
                                    action  = "store_true",
                                    default = True,
                                    help    = "Use the CLI rather then GUI")
        runtime_group.add_option(   "--gui",
                                    dest    = "gui_mode",
                                    action  = "store_true",
                                    default = False,
                                    help    = "Force Revisor to use the GUI. Does not fallback to CLI and thus shows GUI related errors")
        runtime_group.add_option(   "--list-images",
                                    dest    = "list_images",
                                    action  = "store_true",
                                    default = False,
                                    help    = "List available images for a given Jigdo file.")

        ##
        ## Logging Options
        ##
        runtime_group.add_option(   "-d", "--debug",
                                    dest    = "debuglevel",
                                    default = 0,
                                    type    = 'int',
                                    help    = _("Set debugging level (0 by default)"))

        ##
        ## Redundant Options
        ##
        runtime_group.add_option(   "-y", "--yes",
                                    dest    = "answer_yes",
                                    action  = "store_true",
                                    default = False,
                                    help    = _("Answer all questions as 'yes'"))

        ##
        ## Configuration Options
        ##
        config_group = parser.add_option_group(_("Configuration Options"))
        config_group.add_option(    "-c", "--config",
                                    dest    = "config",
                                    action  = "store",
                                    default = os.path.join(BASE_CONF_DIR,"pyjigdo.conf"),
                                    help    = _("PyJigdo configuration file to use"),
                                    metavar = "[config file]")
        config_group.add_option(    "--dest-dir", "--destination-directory",
                                    dest    = "destination_directory",
                                    action  = "store",
                                    default = "/var/tmp/pyjigdo/",
                                    help    = _("Destination directory for products"),
                                    metavar = "[directory]")
        config_group.add_option(    "--work-dir", "--working-directory",
                                    dest    = "working_directory",
                                    action  = "store",
                                    default = "/var/tmp/pyjigdo/",
                                    help    = _("Working directory"),
                                    metavar = "[directory]")

        ## Information Options
        ## Purpose: We should allow a user to query a jigdo and get lots-o-info from just
        ##          downloading the jigdo file.
        general_group = parser.add_option_group(_("General Options"))
        general_group.add_option(   "-j", "--jigdo",
                                    dest    = "jigdo_url",
                                    action  = "store",
                                    default = "",
                                    help    = "Location of jigdo file.",
                                    metavar = "[url]")
        general_group.add_option(   "--info",
                                    dest    = "jigdo_info",
                                    action  = "store_true",
                                    default = False,
                                    help    = "Print information about the jigdo image and exit.")
        general_group.add_option(   "--fallback",
                                    dest    = "fallback_number",
                                    action  = "store",
                                    default = 5,
                                    type    = 'int',
                                    help    = "Number of public mirrors to try before using a fallback mirror. (Default: 5)",
                                    metavar = "[number of tries]")
        general_group.add_option(   "--timeout",
                                    dest    = "urlgrab_timeout",
                                    action  = "store",
                                    default = 15,
                                    type    = 'float',
                                    help    = "Number of seconds to wait before switching to different slice source. (Default: 20)",
                                    metavar = "[number of seconds]")

        ## Downloading Options
        ## Purpose: Allow a user to non-interactively download a defined image or images.
        ##          This should include being able to download all images with one command.
        ##          This is also for download options, like how many threads to use, to cache or not, etc.
        # FIXME: Make --image take a comma seperated list also
        download_group = parser.add_option_group(_("Download Options"))
        download_group.add_option(  "--image",
                                    dest    = "image_numbers",
                                    default = [],
                                    action  = "append",
                                    type    = "int",
                                    help    = "Download or Host given image number(s).",
                                    metavar = "[image number]")
        download_group.add_option(  "--all",
                                    dest    = "image_all",
                                    action  = "store_true",
                                    default = False,
                                    help    = "Download or Host all images defined in jigdo.")
        ## FIXME: Any creative ways to take this data and not limit to just two repos?
        #download_group.add_option(  "--download-mirror-base",
                                    #dest    = "base_download_mirror",
                                    #action  = "store",
                                    #default = "",
                                    #help    = "Download base files from given mirror.",
                                    #metavar = "[mirror url to file root]")
        #download_group.add_option(  "--download-mirror-updates",
                                    #dest    = "updates_download_mirror",
                                    #action  = "store",
                                    #default = "",
                                    #help    = "Download updates files from given mirror.",
                                    #metavar = "[mirror url to file root]")

        # FIXME: We might make it not a choice to cache. It *will* use more space, but much less bandwidth
        #        ate least when building more then one image/set.
        #download_group.add_option("--cache", dest="cache_files", action="store", default=True,
        #                 help="Force caching files to be reused for multiple images. The max space used will be double the resulting image(s) size(s).")
        #download_group.add_option("--nocache", dest="nocache_files", action="store", default=False,
        #                 help="Force caching of files off. This might cause the same file to be downloaded more then once but will use less HDD space while running.")

        #download_group.add_option(  "--threads",
                                    #dest    = "download_threads",
                                    #action  = "store",
                                    #default = "2",
                                    #help    = "Number of threads to use when downloading. (Not in use yet)",
                                    #metavar = "[number]")
        #download_group.add_option(  "--workdir",
                                    #dest    = "download_workdir",
                                    #action  = "store",
                                    #default = "/var/tmp/pyjigdo",
                                    #help    = "Directory to do work in.",
                                    #metavar = "[directory]")

        #
        ## Scan Options
        ## Purpose: Allow a user to specify directories to scan for files, including pointing
        ## to existing ISO image(s)
        #
        #scan_group = parser.add_option_group(_("Scan Options"))
        #scan_group.add_option(      "--scan-dir",
                                    #dest    = "scan_dirs",
                                    #action  = "append",
                                    #type    = "str",
                                    #help    = "Scan given directory for files needed by selected image(s).",
                                    #metavar = "[directory]")
        #scan_group.add_option(      "--scan-iso",
                                    #dest    = "scan_isos",
                                    #action  = "append",
                                    #type    = "str",
                                    #help    = "Mount and then scan existing ISO images for files needed by selected image(s).",
                                    #metavar = "[iso image]")

        #
        ## Hosting Options
        ## Purpose: Allow a user to easily setup a location that contains all the needed
        ##          data defined in the jigdo. Preserve/create directory structure based
        ##          on defined [servers] path data.
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
                                    #dest    = "host_data_directory",
                                    #action  = "store",
                                    #default = "",
                                    #help    = "Directory to download data to.",
                                    #metavar = "[directory]")
        #hosting_group.add_option(   "--host-templates-dir",
                                    #dest    = "host_templates_directory",
                                    #action  = "store",
                                    #default = "",
                                    #help    = "Directory to download templates to.",
                                    #metavar = "[directory]")

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

    def answer_questions(self):
        """Answers questions such as when --jigdo --info has been specified"""
        if self.cli_options.jigdo_info:
            sys.exit(pyjigdo.misc.jigdo_info(self.cli_options.jigdo_url,
                                             self.cli_options.working_directory,
                                             self.base.log))

        if self.cli_options.list_images:
            sys.exit(pyjigdo.misc.list_images(self.cli_options.jigdo_url,
                                              self.cli_options.working_directory,
                                              self.base.log))

    def run(self):
        self.base.run()

## Check options

#building_images = False
#hosting_images = False
#generating_images = False

### FIXME: Here we want to check if we are given enough information by the user,
### or if we are going to need to go interactive to answer more questions.

### FIXME: We most like want this info to go into some sort of config object.

#if options.base_download_mirror or options.updates_download_mirror:
    #print "\n\tSelecting mirrors via options is not supported yet. Sorry.\n"
    #sys.exit(1)

#if options.host_image_numbers:
    #print "\n\tSelecting images via options is not supported yet. Sorry.\n"
    #sys.exit(1)

#if options.host_all and (options.host_data_directory == ""):
    #print "\n\tYou must select a location to host the data defined in this jigdo. Use --host-data-dir\n"
    #sys.exit(1)

#if options.host_all and (options.host_templates_directory == ""):
    #print "\n\tYou must select a location to host the data defined in this jigdo. Use --host-templates-dir\n"
    #sys.exit(1)

#if (options.host_image_numbers or options.host_all or (options.host_data_directory != "") or (options.host_templates_directory != "")) and (options.download_image_numbers or options.download_all):
    #print "\n\tYou can not download and setup hosting at the same time yet. Sorry.\n"
    #sys.exit(1)

#if options.download_image_numbers or options.download_all:
    #building_images = True

#if options.host_image_numbers or options.host_all:
    #hosting_images = True

## FIXME: Workaround, hacktackular, mess
##if options.iso_image_locations:
##    generating_images = True

#if generating_images and (building_images or hosting_images):
    #print "\n\tYou can not generate images at the same time as hosting or building yet. Sorry.\n"
    #sys.exit(1)

#if generating_images:
    ## FIXME: This requires both repos be specified. This also goes back to having a better way
    ## to get this data from the user

    ## FIXME: This really needs to be generic, allowing any number of repos to be speicified.
    #for mirror_location in (options.base_local_mirror, options.updates_local_mirror):
        #if not os.access(mirror_location, os.R_OK):
            #if mirror_location == "":
                #print "\n\tLocal mirrors must be specified. Use --local-mirror-base and --local-mirror-updates\n"
            #else:
                #print "\n\tMirror location %s is not accessible. Exiting.\n" % mirror_location
            #sys.exit(1)
    ## FIXME: Most likely, we would want a dict we can remove elements from if not accessible and
    ## just warn the user, not exit.
    #for iso_image_file in options.iso_image_locations:
        #if not os.access(iso_image_file, os.R_OK):
            #print "\n\tISO % is not accessible. Exiting.\n" % iso_image_file
            #sys.exit(1)
    #if options.generation_directory != "":
        #misc.check_directory(options.generation_directory)
    #else:
        #print "\n\tGeneration directory required. Use --generation-dir\n"
        #sys.exit(1)

    ## FIXME: This is a total hack. (The hack being just sticking this here and then
    ## exiting after done.

    ## FIXME: This needs better juju!
    #jigdo_file_name = os.path.join(options.generation_directory, options.jigdo_name + '.jigdo')
    #for iso_image_file in options.iso_image_locations:
        ## FIXME: We need to generate jigdo.JigdoRepoDefinition()s
        #jigdo.generate_jigdo_template(jigdo_file_name, template_file_name, iso_image_file, repos)
    #print "All done. Jigdo data is in %s" % options.generation_directory
    #sys.exit(1)


## Make download_workdir absolute
## FIXME: This might be breaking. I've seen some strange directory paths
## being created, but don't blame this, yet.
#download_workdir = os.path.abspath(options.download_workdir)
#misc.check_directory(download_workdir)
#options.download_workdir = download_workdir

##Make hosting dirs absolute
#host_data_directory = os.path.abspath(options.host_data_directory)
#host_templates_directory = os.path.abspath(options.host_templates_directory)
#misc.check_directory(host_data_directory)
#misc.check_directory(host_templates_directory)
#options.host_data_directory = host_data_directory
#options.host_templates_directory = host_templates_directory

#user_specified_images = False
#jigdo_file = ""
#if options.jigdo_source == "":
    #print "\n\tNo jigdo file specified. Use --jigdo\n"
    #sys.exit(1)
#else:
    #print "Fetching %s..." % options.jigdo_source
    #file_name, jigdo_local_file, jigdo_file = misc.getFileName(options)

## Init our jigdo_config
## eventually None ==> external mirror list file that we want to merge
#jigdo_config = parse.jigdoDefinition(jigdo_file, None, options.download_workdir)
#jigdo_config.jigdo_url = options.jigdo_source

#if options.show_info_exit:
    #""" Show the user what we know about the jigdo template, and then exit."""
    ## the layout for the jigdoDefinition is the same as the config file
    ## self.SectionName['OptionName'] retrieves a value
    #for section in jigdo_config.getSections():
        #print '** %s:' % section[0]
        #misc.printOut(section[1], 0)
        ##print section[1]
    #sys.exit(1)

#if options.download_image_numbers or options.host_image_numbers:
    #user_specified_images = True

## Ask the user if they would like to scan directories for the needed files, if not passed via CLI
#if options.scan_dirs:
    #for directory in options.scan_dirs:
        #full_path = os.path.abspath(directory)
        #if not os.access(full_path, os.R_OK):
            #print "Directory %s not accessable, will not scan." % full_path
        #else:
            #jigdo_config.scan_dirs.append(full_path)
    #print "These directories will be scanned before downloading any files:"
    #for directory in jigdo_config.scan_dirs:
        #print "\t%s" % directory
#else:
    #adding_scan_dirs = True
    #scan_question = raw_input("Would you like to scan any directories for needed files? [y/N] ")
    #if scan_question.lower() not in ["y", "yes"]: adding_scan_dirs = False
    #while adding_scan_dirs:
        #scan_directory = raw_input("What directory would you like to scan? ")
        #full_path = os.path.abspath(scan_directory)
        #if not os.access(full_path, os.R_OK):
            #print "Directory %s not accessable, will not scan." % full_path
        #else:
            #jigdo_config.scan_dirs.append(full_path)
        #if len(jigdo_config.scan_dirs) > 0: print "Currently going to scan directories: %s" % ", ".join(jigdo_config.scan_dirs)
        #scan_add_more = raw_input("Would you like to add another directory to scan? [y/N] ")
        #if scan_add_more.lower() not in ["y", "yes"]: adding_scan_dirs = False

## Ask the user if they would like to scan ISO images for needed files, if not passed via CLI
#if options.scan_isos:
    #for iso_file in options.scan_isos:
        #full_path = os.path.abspath(iso_file)
        #if not os.access(full_path, os.R_OK):
            #print "ISO image %s not accessable, will not scan." % full_path
        #else:
            #jigdo_config.scan_isos.append(misc.LoopbackMount(full_path,
                                          #os.path.join(options.download_workdir, "mounts", os.path.basename(full_path)),
                                          #"iso9660"))
    #print "These ISO images will be scanned before downloading any files:"
    #for iso_file in jigdo_config.scan_isos:
        #print "\t%s" % iso_file["iso"]
#else:
    #adding_iso_images = True
    #scan_question = raw_input("Would you like to scan any iso images for needed files? [y/N] ")
    #if scan_question.lower() not in ["y", "yes"]: adding_iso_images = False
    #while adding_iso_images:
        #scan_directory = raw_input("What ISO image would you like to scan? ")
        #full_path = os.path.abspath(scan_directory)
        #if not os.access(full_path, os.R_OK):
            #print "ISO image %s not accessable, will not scan." % full_path
        #else:
            #jigdo_config.scan_isos.append(misc.LoopbackMount(full_path,
                                          #os.path.join(options.download_workdir, "mounts", os.path.basename(full_path)),
                                          #"iso9660"))
        #if len(jigdo_config.scan_isos) > 0:
            #print "These ISO images will be scanned before downloading any files:"
            #for iso_file in jigdo_config.scan_isos:
                #print "\t%s" % iso_file["iso"]
        #scan_add_more = raw_input("Would you like to add another ISO image to scan? [y/N] ")
        #if scan_add_more.lower() not in ["y", "yes"]: adding_iso_images = False

## Ask the user what images they want to download
#active_images = []
#if not user_specified_images and not options.download_all and not options.host_all:
    #choosing_images = True
    #while choosing_images:
        #misc.printOut(jigdo_config.Images, 0)
        #num_images = len(jigdo_config.Images)
        #image_choice = raw_input("What image(s) would you like to download? [1-%s] " % num_images )
        #if image_choice == "":
            #print "You must select at least one image to download..."
            #continue
        #image_choice_filter = image_choice.replace(',', ' ')
        #image_choices = image_choice_filter.split(' ')
        #for choice in image_choices:
            #if choice == '': continue
            #try:
                #if int(choice) > num_images:
                    #print "Image number %s not found." % choice
                #elif choice not in active_images:
                    #active_images.append(choice)
            #except ValueError:
                #print "Input %s is not a valid selection." % choice
        #print "Currently going to download image(s): %s" % ", ".join(active_images)
        #continue_selecting = raw_input("Would you like to select another image for download? [y/N] ")
        #if continue_selecting.lower() not in ["y", "yes"]:
            #choosing_images = False
    #if len(active_images) < 1:
        ## FIXME: Don't be so brutal, let the user try again from this point.
        #print "You must select an image to download. Exiting."
        #sys.exit(1)
    #building_images = True
#elif options.download_all or options.host_all:
    #print "Downloading/Hosting all images selected, adding all images..."
    #for image_id in jigdo_config.Images:
        #active_images.append(str(image_id))
#elif user_specified_images:
    #print "Adding selected images to download..."
    #for image_selection in (options.download_image_numbers + options.host_image_numbers):
        #if int(image_selection) in jigdo_config.Images:
            #active_images.append(image_selection)
        #else:
            #print "Image number %s not found, not adding." % image
    #if len(active_images) < 1:
        #print "No images could be found. Exiting."
        #sys.exit(1)
    #else:
        #print "Going to download image(s): %s" % ", ".join(active_images)

## Ask the user what mirror source to host
## FIXME: Parse jigdo_config.Servers and offer selecting what mirror source to host
#mirror_server_ids = []
#if hosting_images:
    #server_ids = {}
    #current_id = 0
    #print "\nJigdo Requested Sources:\n"
    #for sid in jigdo_config.Servers:
        #current_id += 1
        #server_ids[str(current_id)] = sid
        #print "\t%s: %s" % (current_id, sid)
    #choosing_servers = True
    #while choosing_servers:
        #num_servers = len(server_ids)
        #server_choice = raw_input("\nWhat server ID(s) would you like to download? [1-%s] (Default: All) " % num_servers )
        #if server_choice == "":
            #for sid in server_ids:
                #mirror_server_ids.append(server_ids[sid])
            #break
        #server_choice_filter = server_choice.replace(',', ' ')
        #server_choices = server_choice_filter.split(' ')
        #for choice in server_choices:
            #if choice == '': continue
            #try:
                #if int(choice) > num_servers:
                    #print "Source number %s not found." % choice
                #elif server_ids[choice] not in mirror_server_ids:
                    #mirror_server_ids.append(server_ids[choice])
            #except ValueError:
                #print "Input %s is not a valid selection." % choice
        #print "Currently going to host source(s): %s" % ", ".join(mirror_server_ids)
        #continue_selecting = raw_input("Would you like to select another source for hosting? [y/N] ")
        #if continue_selecting.lower() not in ["y", "yes"]:
            #choosing_servers = False

## Ask user what mirror to use.
## FIXME: We want to ask the user if they have a mirror preference. We will only ask
## if they have not defined a specific mirror. Here we basically offer "auto" or a
## selection from the mirrorlist. The mirrorlist url should be provided in the jigdo
## template, and for now this information will need to be manually added to the jigdo
## as jigdo-file doesn't care. We might need to push this upstream when it works well.

## Build the mirror lists.
#jigdo_config.buildMirrors()

#preferred_mirrors = []
#if options.base_download_mirror or options.updates_download_mirror:
    ## FIXME: This needs some magic. We can use preferred_mirrors as the array will
    ## preserve the selection order. preferred_mirrors are used first when trying to
    ## download a slice.
    #pass
#else:
    #if len(jigdo_config.mirror_fallback.keys()) > 0: print "\nJigdo Provided Mirror Sources:\n"
    #if len(jigdo_config.mirror_fallback.keys()) > 20: print "\nMore then 20 Sources, truncating list:\n"

    #i = 0
    #for mirror in jigdo_config.mirror_fallback.keys():
        #i += 1
        #print "\t%s: '%s' - %s" % (mirror, jigdo_config.mirror_fallback[mirror][0], jigdo_config.mirror_fallback[mirror][1])
        #if i > 19: break

    #if len(jigdo_config.mirror_geo.keys()) > 0: print "\nGeoIP Based Mirrors (from mirror list):\n"
    #for mirror in jigdo_config.mirror_geo.keys():
        #print "\t%s: '%s' - %s" % (mirror, jigdo_config.mirror_geo[mirror][0], jigdo_config.mirror_geo[mirror][1])

    #if len(jigdo_config.mirror_global.keys()) > 0:
        #print "\n\tNot showing %s global fallback mirrors. They will be scanned last.\n" % len(jigdo_config.mirror_global.keys())

    ## FIXME: If we can find a better way to display this info, we should. In a GUI it can be shown, but in the CLI it is
    ## just too much data.
    ##for mirror in jigdo_config.mirror_global.keys():
    ##    print "\t%s: '%s' - %s" % (mirror, jigdo_config.mirror_global[mirror][0], jigdo_config.mirror_global[mirror][1])

    #user_chose_mirrors = raw_input("\nWould you like to select a specific mirror to download from? (Default: Use all, closest first) [y/N] ")
    #if user_chose_mirrors.lower() in ["y", "yes"]:
        #choosing_mirrors = True
        #while choosing_mirrors:
            #mirror_choice = raw_input("What mirror(s) would you like to use? [1-%s] " % jigdo_config.mirror_num)
            #mirror_choice_filter = mirror_choice.replace(',', ' ')
            #mirror_choices = mirror_choice_filter.split(' ')
            #for choice in mirror_choices:
                #if choice == '': continue
                #try:
                    #if int(choice) > jigdo_config.mirror_num:
                        #print "Mirror number %s not found." % choice
                    #elif choice not in preferred_mirrors:
                        #preferred_mirrors.append(choice)
                #except ValueError:
                    #print "Input %s is not a valid selection." % choice
            #print "Currently going to download from: %s" % ", ".join(preferred_mirrors)
            #continue_selecting = raw_input("Would you like to select another mirror? [y/N] ")
            #if continue_selecting.lower() not in ["y", "yes"]:
                #choosing_mirrors = False

## Push user selection into a preferred list for use when downloading
#for mirror in preferred_mirrors:
    #server_id = ""
    #url = ""
    #try:
        #(server_id, url) = jigdo_config.mirror_fallback[mirror]
    #except KeyError:
        #pass
    #try:
        #(server_id, url) = jigdo_config.mirror_geo[mirror]
    #except KeyError:
        #pass
    #try:
        #(server_id, url) = jigdo_config.mirror_global[mirror]
    #except KeyError:
        #pass
    #jigdo_config.mirror_preferred[mirror] = [server_id, url]


## At this point we should be ready to start actually downloading.
## FIXME: We need to create a job pool. This should allow us to async the download
## using urlgrabber. We also should record what has happened with each file.
## Example, 200 "done", 404 "mirror source no good".



## FIXME: Maybe just require a jigdo_config... my thinking was that we might want to
## feed parts another way and want to leave open that ability.
#template_slices = image.TemplateSlices(jigdo_config, jigdo_config.Parts)


## FIXME: This is just an example.
#test_jobs = JigdoJobsPool(jigdo_config, template_slices, file_name)

#if building_images:
    ## don't use for image, because it overwrites namespace.
    ##for image in jigdo_config.Images.keys():
    #for selected_image in jigdo_config.Images.keys():
        #if str(selected_image) in active_images:
            #iso = jigdo_config.Images[selected_image]
            ## FIXME: Support all [Image] metadata
            #test_jobs.initISO(iso["Template-MD5Sum"], iso["Template"], iso["Filename"])

    #test_jobs.getISOslices()
    #for directory in jigdo_config.scan_dirs:
        #test_jobs.scan_dir(directory)
    #for iso_image_file in jigdo_config.scan_isos:
        #iso_image_file.mount()
        #test_jobs.scan_dir(iso_image_file.location)
        #iso_image_file.umount()
    #"""for iso_image in test_jobs.images:
            ### Ok, we have iso_image which is an ISOImage object ready to go. Just an example.
            ### We would want this to go into a queue and be blown away by threads ;-)
            #print "Downloading needed slices for %s..." % iso_image.location
            #num_download = len(iso_image.image_slices.keys()) + 1
            #for num, image_slice in enumerate(iso_image.image_slices.iterkeys()):
                #print iso_image.image_slices[image_slice]"""
    ## ^ = all false... so it's after here
    ## This is actually doing what it's supposed to do.
    ## It checks and updates our python objects based on what all our scan_dir() calls were able to do.
    #test_jobs.checkISOslices()
    ## At this point, we should be ready to just download what the scan_dir() calls could not find.

    #test_jobs.run(options.download_threads)

    #for isoimage in test_jobs.images:
        #print "Image defined by template %s is located %s" % (isoimage.template, isoimage.location)
        #print "Checking if sums match..."
        #if isoimage.checkImage():
            #print "Sums match. Image %s is complete." % isoimage.location
            #isoimage.finished = True
        #else:
            #print "Sums don't match. Image %s is not complete." % isoimage.location
            ## FIXME: Return values?
            #isoimage.finished = False

#if hosting_images:
    ## FIXME: Make it so this will actually scan stuff.
    #for directory in jigdo_config.scan_dirs:
        #print "Not able to scan %s yet. Sorry." % directory
    #for iso_image_file in jigdo_config.scan_isos:
        #print "Not able to scan % yet. Sorry." % iso_image_file.location

    ## FIXME: Support only hosting specific images (based on templates)
    ## This just downloads what matches the selected server ids.

    #for selected_image in jigdo_config.Images.keys():
        #if str(selected_image) in active_images:
            #iso = jigdo_config.Images[selected_image]
            #test_jobs.initISO(iso["Template-MD5Sum"], iso["Template"], iso["Filename"])

    #num_slices = len(template_slices.slices)
    #counter = 0
    #for image_slice_sum in template_slices.slices:
        #counter += 1
        #image_slice_object = template_slices.slices[image_slice_sum]
        #if image_slice_object.server_id in mirror_server_ids:
            #while not image.download_slice(image_slice_object.slice_sum, counter, num_slices,
                                           #jigdo_config, template_slices, file_name,
                                           #local_dir=options.host_data_directory):
                ## Cheap hack to make it run until ^ works
                #pass
        #else:
            #print "[%s/%s] %s not found via selected server id(s), not downloading..." % (counter, num_slices, image_slice_object.file_name)
    #print "\nAll found files downloaded to %s." % options.host_data_directory

# This is where the fun begins
if __name__ == "__main__":
    pyjigdo = PyJigdo()

