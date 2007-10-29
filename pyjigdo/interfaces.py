#!/usr/bin/python
#
# Copyright 2007 Fedora Unity
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
"""
Anything to do with interfacing with a human. Natrually, program switches go
here.
"""

import rhpl.translate as translate
from rhpl.translate import _, N_

from optparse import OptionParser
parser = OptionParser()

#
## Information Options
## Purpose: We should allow a user to query a jigdo and get lots-o-info from just
##          downloading the jigdo file.
#
general_group = parser.add_option_group(_("General Options"))
general_group.add_option("--jigdo", dest="jigdo_source", action="store", default="",
                 help="Location of jigdo file.", metavar="[url to jigdo file]")
general_group.add_option("--info", dest="show_info_exit", action="store_true", default=False,
                 help="Print information about the jigdo image and exit.")
general_group.add_option("--debug", dest="debug", action="store_true", default=False,
                 help="Enable debug printing.")
general_group.add_option("--fallback", dest="fallback_number", action="store", default=5,
                 help="Number of public mirrors to try before using a fallback mirror. (Default: 5)", metavar="[number of tries]")

#
## Downloading Options
## Purpose: Allow a user to non-interactively download a defined image or images.
##          This should include being able to download all images with one command.
##          This is also for download options, like how many threads to use, to cache or not, etc.
#
download_group = parser.add_option_group(_("Download Options"))
download_group.add_option("--download-image", dest="download_image_numbers", default=[], action="append", type="str",
                 help="Download given image number.", metavar="[image number]")
download_group.add_option("--download-all", dest="download_all", action="store_true", default=False,
                 help="Download all images defined in jigdo.")
# FIXME: Any creative ways to take this data and not limit to just two repos?
download_group.add_option("--download-mirror-base", dest="base_download_mirror", action="store", default="",
                 help="Download base files from given mirror.", metavar="[mirror url to file root]")
download_group.add_option("--download-mirror-updates", dest="updates_download_mirror", action="store", default="",
                 help="Download updates files from given mirror.", metavar="[mirror url to file root]")

# FIXME: We might make it not a choice to cache. It *will* use more space, but much less bandwidth
#        ate least when building more then one image/set.
#download_group.add_option("--cache", dest="cache_files", action="store", default=True,
#                 help="Force caching files to be reused for multiple images. The max space used will be double the resulting image(s) size(s).")
#download_group.add_option("--nocache", dest="nocache_files", action="store", default=False,
#                 help="Force caching of files off. This might cause the same file to be downloaded more then once but will use less HDD space while running.")

download_group.add_option("--threads", dest="download_threads", action="store", default="2",
                 help="Number of threads to use when downloading.", metavar="[number]")
download_group.add_option("--workdir", dest="download_workdir", action="store", default="/var/tmp/pyjigdo",
                 help="Directory to do work in.", metavar="[directory]")

#
## Scan Options
## Purpose: Allow a user to specify directories to scan for files, including pointing
## to existing ISO image(s)
#
scan_group = parser.add_option_group(_("Scan Options"))
scan_group.add_option("--scan-dir", dest="scan_dirs", action="append", type="str",
                 help="Scan given directory for files needed by selected image(s).", metavar="[directory]")
scan_group.add_option("--scan-iso", dest="scan_isos", action="append", type="str",
                 help="Mount and then scan existing ISO images for files needed by selected image(s).", metavar="[iso image]")

#
## Hosting Options
## Purpose: Allow a user to easily setup a location that contains all the needed
##          data defined in the jigdo. Preserve/create directory structure based
##          on defined [servers] path data.
#
hosting_group = parser.add_option_group(_("Hosting Options"))
hosting_group.add_option("--host-image", dest="host_image_numbers", default=[], action="append", type="str",
                 help="Host given image number.", metavar="[image number]")
hosting_group.add_option("--host-all", dest="host_all", action="store_true", default=False,
                 help="Host all images defined in jigdo.")
hosting_group.add_option("--host-dir", dest="host_directory", action="store", default="",
                 help="Directory to download data to.", metavar="[directory]")

#
## Generation Options
## Purpose: Allow a user to generate jigdo configs and templates.
generation_group = parser.add_option_group(_("Generation Options"))
generation_group.add_option("--iso-image", dest="iso_image_locations", default=[], action="append", type="str",
                 help="Build jigdo for given ISO image.", metavar="[image location]")
# FIXME: Any creative ways to take this data and not limit to just two repos?
# We need a way to be able to say "ISO 1 needs repo 1 and repo 2 found here and there with labels 1 and 2"
# What I've done here will require a command to pyjigdo per arch, kinda clunky
generation_group.add_option("--local-mirror-base", dest="base_local_mirror", action="store", default="",
                 help="Find base files from given local mirror.", metavar="[local location for base files]")
generation_group.add_option("--local-mirror-updates", dest="updates_local_mirror", action="store", default="",
                 help="Find updates files from given local mirror.", metavar="[local location for updates files]")
generation_group.add_option("--mirror-base-label", dest="base_local_label", action="store", default="Base",
                 help="Label for local mirror source 'base'. Default 'Base'", metavar="[label]")
generation_group.add_option("--mirror-updates-label", dest="updates_local_label", action="store", default="Updates",
                 help="Label for local mirror source 'updates'. Default 'Updates'", metavar="[label]")
generation_group.add_option("--generation-dir", dest="generation_directory", action="store", default="",
                 help="Directory to dump generated jigdo(s) into.", metavar="[directory]")
generation_group.add_option("--jigdo-name", dest="jigdo_name", action="store", default="pyjigdo-generated",
                 help="Name to give this jigdo. Result will be 'name'.jigdo", metavar="[name]")


# Parse Options
(options, args) = parser.parse_args()
