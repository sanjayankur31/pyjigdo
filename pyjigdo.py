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
import os
import sys

import rhpl.translate as translate
from rhpl.translate import _, N_

from urlgrabber import urlgrab
from urlgrabber.grabber import URLGrabError
from urlgrabber.progress import TextMeter
from urlparse import urlparse
from urlparse import urljoin
from urlgrabber import urlread

from pyjigdo import interfaces
from pyjigdo import parse
from pyjigdo import image
from pyjigdo import misc
options = misc.options


# not needed *yet*
#from rhpl.translate import _, N_
#import distutils, distutils.sysconfig
#import threading
#import thread
#import Queue
#import subprocess
#import select


# FIXME: This is nothing but a test for working with the objects we have so far.
# We will want to subclass the pool.py
class SimpleTestJobDesign:
    """ This is just a test class for building our objects and looping them. """
    def __init__(self, jigdo_config, template_slices, file_name):
        """ Get our storage setup. """
        self.images = []
        self.jigdo_config = jigdo_config
        self.template_slices = template_slices
        self.file_name = file_name
        self.clearCache()

    def clearCache(self):
        """ Delete any files needing to be cleared from any previous run. """
        #if os.path.isfile(self.jigdo_config.cache_db):
        #    os.remove(self.jigdo_config.cache_db)
        pass

    def run(self, threads):
        """ Run the download with N threads. """
        """ This is just going to call a download on each item."""
        print "\nRunning needed actions...\n"
        # Make sure we have a cache dir.
        misc.check_directory(self.jigdo_config.cache_dir)
        for iso_image in self.images:
            ## Ok, we have iso_image which is an ISOImage object ready to go. Just an example.
            ## We would want this to go into a queue and be blown away by threads ;-)
            if not iso_image.finished:
                print "Downloading needed slices for %s..." % iso_image.location
                num_download = len(iso_image.image_slices.keys()) + 1
                for num, image_slice in enumerate(iso_image.image_slices.iterkeys()):
                    if not iso_image.image_slices[image_slice]:
                        while not iso_image.downloadSlice(image_slice,
                                                      num+1,
                                                      num_download,
                                                      self.jigdo_config,
                                                      self.template_slices,
                                                      self.file_name):
                            # Cheap hack to make it run until ^ works
                            pass

        # FIXME: Put it all together
        # We need to run some checks to make sure we have all the slices, maybe md5sum
        # checking, but jigdo will do this on its own. We should maybe only check sums
        # after we feed the downloaded data to jigdo, it rejects it and we want to check
        # for ourselves. The md5 infrastructure is here for when we start moving away from
        # jigdo-file for actually putting things back together.
        # 20071018: Checking MD5 is now done (part of download_slice itself)
        
        # Have jigdo-file start stuffing data where it needs to go.
        self.scan_dir(self.jigdo_config.cache_dir)
        
        # FIXME: We need to check that everything got put together and mark it as finished.
        # Maybe some other cool logic also. Examples: offer cleanup, cleanup mounts (if any)
        # offer to sum the iso image against a signed sha1sum, etc.

    def initISO(self, template_md5, template, file_name):
        """ Add an ISOImage to the queue. """
        template_url = ""
        if urlparse(template)[0] == "":
            template_url = urljoin(self.jigdo_config.jigdo_url, template)
        else:
            template_url = template
        try:
            local_template = os.path.join(options.download_workdir, "images", "%s.template" % file_name)
            iso_location = os.path.join(options.download_workdir, "images", file_name)
            misc.check_directory(os.path.dirname(local_template))
            misc.check_directory(os.path.dirname(iso_location))
            template_local = False
            if os.path.isfile(local_template):
                print "Template %s exists, checking if complete..." % local_template
                if misc.compare_sum(local_template, template_md5):
                    print "Template is complete."
                    template_local = True
                else:
                    print "Template is not complete..."
            if not template_local:
                print "Fetching template %s" % template_url
                urlgrab(template_url, filename=local_template, progress_obj=TextMeter())
            if template_local or misc.compare_sum(local_template, template_md5):
                isoimage = image.ISOImage(local_template, template_md5, iso_location)
                isoimage.download = True
                self.images.append(isoimage)
        except URLGrabError:
            print "Failed fetching %s, not building image..." % template_url

    def getISOslices(self):
        """ Get the slices we need to deal with. """
        for iso_image in self.images:
            iso_image.getSlices()

    def checkISOslices(self):
        """ Check to see what has been added to the ISO and update remaining files. """
        for iso_image in self.images:
            iso_image.checkSlices(self.template_slices)

    def scan_dir(self, directory):
        """ Scan a directory for local files that wont need to be downloaded. """
        for iso_image in self.images:
            misc.check_directory(os.path.dirname(iso_image.location))
            print "Scanning directory %s for files needed by %s..." % (directory, iso_image.location)
            # FIXME: Try to guess how long, maybe make a task list, or even better pipe the output
            # from the jigdo-lite command somewhere.
            print "This is going to take some time, please wait..."
            misc.run_command(["jigdo-file", "make-image",
                        "--cache", self.jigdo_config.cache_db,
                        "--image", iso_image.location,
                        "--jigdo", self.jigdo_config.definition_file_loc,
                        "--template", iso_image.template,
                        "-r", "quiet",
                        "--force",
                        directory],
                        inshell=True)
# Check options

building_images = False
hosting_images = False
generating_images = False

## FIXME: Here we want to check if we are given enough information by the user,
## or if we are going to need to go interactive to answer more questions.

## FIXME: We most like want this info to go into some sort of config object.

if options.base_download_mirror or options.updates_download_mirror:
    print "\n\tSelecting mirrors via options is not supported yet. Sorry.\n"
    sys.exit(1)

if options.host_image_numbers:
    print "\n\tSelecting images via options is not supported yet. Sorry.\n"
    sys.exit(1)

if options.host_all and (options.host_data_directory == ""):
    print "\n\tYou must select a location to host the data defined in this jigdo. Use --host-data-dir\n"
    sys.exit(1)

if options.host_all and (options.host_templates_directory == ""):
    print "\n\tYou must select a location to host the data defined in this jigdo. Use --host-templates-dir\n"
    sys.exit(1)

if (options.host_image_numbers or options.host_all or (options.host_data_directory != "") or (options.host_templates_directory != "")) and (options.download_image_numbers or options.download_all):
    print "\n\tYou can not download and setup hosting at the same time yet. Sorry.\n"
    sys.exit(1)

if options.download_image_numbers or options.download_all:
    building_images = True

if options.host_image_numbers or options.host_all:
    hosting_images = True

if options.iso_image_locations:
    generating_images = True

if generating_images and (building_images or hosting_images):
    print "\n\tYou can not generate images at the same time as hosting or building yet. Sorry.\n"
    sys.exit(1)

if generating_images:
    # FIXME: This requires both repos be specified. This also goes back to having a better way
    # to get this data from the user
    for mirror_location in (options.base_local_mirror, options.updates_local_mirror):
        if not os.access(mirror_location, os.R_OK):
            if mirror_location == "":
                print "\n\tLocal mirrors must be specified. Use --local-mirror-base and --local-mirror-updates\n"
            else:
                print "\n\tMirror location %s is not accessible. Exiting.\n" % mirror_location
            sys.exit(1)
    # FIXME: Most likely, we would want a dict we can remove elements from if not accessible and
    # just warn the user, not exit.
    for iso_image_file in options.iso_image_locations:
        if not os.access(iso_image_file, os.R_OK):
            print "\n\tISO % is not accessible. Exiting.\n" % iso_image_file
            sys.exit(1)
    if options.generation_directory != "":
        misc.check_directory(options.generation_directory)
    else:
        print "\n\tGeneration directory required. Use --generation-dir\n"
        sys.exit(1)

    # FIXME: This is a total hack. (The hack being just sticking this here and then
    # exiting after done.

    # FIXME: This needs better juju
    jigdo_file_name = os.path.join(options.generation_directory, options.jigdo_name + '.jigdo')
    for iso_image_file in options.iso_image_locations:
        init_jigdo_location_command = "/bin/touch %s" % jigdo_file_name
        misc.run_command(init_jigdo_location_command)
        generation_command = "/usr/bin/jigdo-file make-template --image=%s %s/ %s/ --label %s=%s --label %s=%s --jigdo=%s --template=%s --no-servers-section --force --merge=%s"
        misc.run_command(generation_command % (iso_image_file,
                        options.base_local_mirror,
                        options.updates_local_mirror,
                        options.base_local_label,
                        options.base_local_mirror,
                        options.updates_local_label,
                        options.updates_local_mirror,
                        jigdo_file_name,
                        os.path.join(options.generation_directory, iso_image_file + '.template'),
                        jigdo_file_name
                        ))
    print "All done. Jigdo data is in %s" % options.generation_directory
    sys.exit(1)


# Make download_workdir absolute
# FIXME: This might be breaking. I've seen some strange directory paths
# being created, but don't blame this, yet.
download_workdir = os.path.abspath(options.download_workdir)
misc.check_directory(download_workdir)
options.download_workdir = download_workdir

user_specified_images = False
jigdo_file = ""
if options.jigdo_source == "":
    print "\n\tNo jigdo file specified. Use --jigdo\n"
    sys.exit(1)
else:
    print "Fetching %s..." % options.jigdo_source
    file_name, jigdo_local_file, jigdo_file = misc.getFileName(options)

# Init our jigdo_config
# eventually None ==> external mirror list file that we want to merge
jigdo_config = parse.jigdoDefinition(jigdo_file, None)
jigdo_config.jigdo_url = options.jigdo_source

if options.show_info_exit:
    """ Show the user what we know about the jigdo template, and then exit."""
    # the layout for the jigdoDefinition is the same as the config file
    # self.SectionName['OptionName'] retrieves a value
    for section in jigdo_config.getSections():
        print '** %s:' % section[0]
        misc.printOut(section[1], 0)
        #print section[1]
    sys.exit(1)

if options.download_image_numbers or options.host_image_numbers:
    user_specified_images = True

# Ask the user if they would like to scan directories for the needed files, if not passed via CLI
if options.scan_dirs:
    for directory in options.scan_dirs:
        full_path = os.path.abspath(directory)
        if not os.access(full_path, os.R_OK):
            print "Directory %s not accessable, will not scan." % full_path
        else:
            jigdo_config.scan_dirs.append(full_path)
    print "These directories will be scanned before downloading any files:"
    for directory in jigdo_config.scan_dirs:
        print "\t%s" % directory
else:
    adding_scan_dirs = True
    scan_question = raw_input("Would you like to scan any directories for needed files? [y/N] ")
    if scan_question.lower() not in ["y", "yes"]: adding_scan_dirs = False
    while adding_scan_dirs:
        scan_directory = raw_input("What directory would you like to scan? ")
        full_path = os.path.abspath(scan_directory)
        if not os.access(full_path, os.R_OK):
            print "Directory %s not accessable, will not scan." % full_path
        else:
            jigdo_config.scan_dirs.append(full_path)
        if len(jigdo_config.scan_dirs) > 0: print "Currently going to scan directories: %s" % ", ".join(jigdo_config.scan_dirs)
        scan_add_more = raw_input("Would you like to add another directory to scan? [y/N] ")
        if scan_add_more.lower() not in ["y", "yes"]: adding_scan_dirs = False

# Ask the user if they would like to scan ISO images for needed files, if not passed via CLI
if options.scan_isos:
    for iso_file in options.scan_isos:
        full_path = os.path.abspath(iso_file)
        if not os.access(full_path, os.R_OK):
            print "ISO image %s not accessable, will not scan." % full_path
        else:
            jigdo_config.scan_isos.append(misc.LoopbackMount(full_path,
                                          os.path.join(options.download_workdir, "mounts", os.path.basename(full_path)),
                                          "iso9660"))
    print "These ISO images will be scanned before downloading any files:"
    for iso_file in jigdo_config.scan_isos:
        print "\t%s" % iso_file["iso"]
else:
    adding_iso_images = True
    scan_question = raw_input("Would you like to scan any iso images for needed files? [y/N] ")
    if scan_question.lower() not in ["y", "yes"]: adding_iso_images = False
    while adding_iso_images:
        scan_directory = raw_input("What ISO image would you like to scan? ")
        full_path = os.path.abspath(scan_directory)
        if not os.access(full_path, os.R_OK):
            print "ISO image %s not accessable, will not scan." % full_path
        else:
            jigdo_config.scan_isos.append(misc.LoopbackMount(full_path,
                                          os.path.join(options.download_workdir, "mounts", os.path.basename(full_path)),
                                          "iso9660"))
        if len(jigdo_config.scan_isos) > 0:
            print "These ISO images will be scanned before downloading any files:"
            for iso_file in jigdo_config.scan_isos:
                print "\t%s" % iso_file["iso"]
        scan_add_more = raw_input("Would you like to add another ISO image to scan? [y/N] ")
        if scan_add_more.lower() not in ["y", "yes"]: adding_iso_images = False

# Ask the user what images they want to download
active_images = []
if not user_specified_images and not options.download_all and not options.host_all:
    choosing_images = True
    while choosing_images:
        misc.printOut(jigdo_config.Images, 0)
        num_images = len(jigdo_config.Images)
        image_choice = raw_input("What image(s) would you like to download? [1-%s] " % num_images )
        if image_choice == "":
            print "You must select at least one image to download..."
            continue
        image_choices = image_choice.split(' ')
        for choice in image_choices:
            try:
                if int(choice) > num_images:
                    print "Image number %s not found." % choice
                elif choice not in active_images:
                    active_images.append(choice)
            except ValueError:
                print "Input %s is not a valid selection." % choice
        print "Currently going to download image(s): %s" % ", ".join(active_images)
        continue_selecting = raw_input("Would you like to select another image for download? [y/N] ")
        if continue_selecting.lower() not in ["y", "yes"]:
            choosing_images = False
    if len(active_images) < 1:
        # FIXME: Don't be so brutal, let the user try again from this point.
        print "You must select an image to download. Exiting."
        sys.exit(1)
    building_images = True
elif options.download_all or options.host_all:
    print "Downloading/Hosting all images selected, adding all images..."
    for image_id in jigdo_config.Images:
        active_images.append(image_id)
elif user_specified_images:
    print "Adding selected images to download..."
    for image_selection in (options.download_image_numbers + options.host_image_numbers):
        if int(image_selection) in jigdo_config.Images:
            active_images.append(image_selection)
        else:
            print "Image number %s not found, not adding." % image
    if len(active_images) < 1:
        print "No images could be found. Exiting."
        sys.exit(1)
    else:
        print "Going to download image(s): %s" % ", ".join(active_images)

# Ask the user what mirror source to host
# FIXME: Parse jigdo_config.Servers and offer selecting what mirror source to host
mirror_server_ids = []
if hosting_images:
    server_ids = {}
    current_id = 0
    print "\nJigdo Requested Sources:\n"
    for sid in jigdo_config.Servers:
        current_id += 1
        server_ids[str(current_id)] = sid
        print "\t%s: %s" % (current_id, sid)
    choosing_servers = True
    while choosing_servers:
        num_servers = len(server_ids)
        server_choice = raw_input("\nWhat server ID(s) would you like to download? [1-%s] (Default: All) " % num_servers )
        if server_choice == "":
            for sid in server_ids:
                mirror_server_ids.append(server_ids[sid])
            break
        server_choices = server_choice.split(' ')
        for choice in server_choices:
            try:
                if int(choice) > num_servers:
                    print "Source number %s not found." % choice
                elif server_ids[choice] not in mirror_server_ids:
                    mirror_server_ids.append(server_ids[choice])
            except ValueError:
                print "Input %s is not a valid selection." % choice
        print "Currently going to host source(s): %s" % ", ".join(mirror_server_ids)
        continue_selecting = raw_input("Would you like to select another source for hosting? [y/N] ")
        if continue_selecting.lower() not in ["y", "yes"]:
            choosing_servers = False

# Ask user what mirror to use.
# FIXME: We want to ask the user if they have a mirror preference. We will only ask
# if they have not defined a specific mirror. Here we basically offer "auto" or a
# selection from the mirrorlist. The mirrorlist url should be provided in the jigdo
# template, and for now this information will need to be manually added to the jigdo
# as jigdo-file doesn't care. We might need to push this upstream when it works well.

# Build the mirror lists.
jigdo_config.buildMirrors()

preferred_mirrors = []
if options.base_download_mirror or options.updates_download_mirror:
    # FIXME: This needs some magic. We can use preferred_mirrors as the array will
    # preserve the selection order. preferred_mirrors are used first when trying to
    # download a slice.
    pass
else:
    if len(jigdo_config.mirror_fallback.keys()) > 0: print "\nJigdo Provided Mirror Sources:\n"
    for mirror in jigdo_config.mirror_fallback.keys():
        print "\t%s: '%s' - %s" % (mirror, jigdo_config.mirror_fallback[mirror][0], jigdo_config.mirror_fallback[mirror][1])

    if len(jigdo_config.mirror_geo.keys()) > 0: print "\nGeoIP Based Mirrors (from mirror list):\n"
    for mirror in jigdo_config.mirror_geo.keys():
        print "\t%s: '%s' - %s" % (mirror, jigdo_config.mirror_geo[mirror][0], jigdo_config.mirror_geo[mirror][1])

    if len(jigdo_config.mirror_global.keys()) > 0:
        print "\n\tNot showing %s global fallback mirrors. They will be scanned last.\n" % len(jigdo_config.mirror_global.keys())

    # FIXME: If we can find a better way to display this info, we should. In a GUI it can be shown, but in the CLI it is
    # just too much data.
    #for mirror in jigdo_config.mirror_global.keys():
    #    print "\t%s: '%s' - %s" % (mirror, jigdo_config.mirror_global[mirror][0], jigdo_config.mirror_global[mirror][1])

    user_chose_mirrors = raw_input("\nWould you like to select a specific mirror to download from? (Default: Use all, closest first) [y/N] ")
    if user_chose_mirrors.lower() in ["y", "yes"]:
        choosing_mirrors = True
        while choosing_mirrors:
            mirror_choice = raw_input("What mirror(s) would you like to use? [1-%s] " % jigdo_config.mirror_num)
            mirror_choices = server_choice.split(' ')
            for choice in mirror_choices:
                try:
                    if int(choice) > jigdo_config.mirror_num:
                        print "Mirror number %s not found." % choice
                    elif choice not in preferred_mirrors:
                        preferred_mirrors.append(choice)
                except ValueError:
                    print "Input %s is not a valid selection." % choice
            print "Currently going to download from: %s" % ", ".join(preferred_mirrors)
            continue_selecting = raw_input("Would you like to select another mirror? [y/N] ")
            if continue_selecting.lower() not in ["y", "yes"]:
                choosing_mirrors = False

# Push user selection into a preferred list for use when downloading
for mirror in preferred_mirrors:
    server_id = ""
    url = ""
    try:
        (server_id, url) = jigdo_config.mirror_fallback[mirror]
    except KeyError:
        pass
    try:
        (server_id, url) = jigdo_config.mirror_geo[mirror]
    except KeyError:
        pass
    try:
        (server_id, url) = jigdo_config.mirror_global[mirror]
    except KeyError:
        pass
    jigdo_config.mirror_preferred[mirror] = [server_id, url]


# At this point we should be ready to start actually downloading.
# FIXME: We need to create a job pool. This should allow us to async the download
# using urlgrabber. We also should record what has happened with each file.
# Example, 200 "done", 404 "mirror source no good".



# FIXME: Maybe just require a jigdo_config... my thinking was that we might want to
# feed parts another way and want to leave open that ability.
template_slices = image.TemplateSlices(jigdo_config, jigdo_config.Parts)


# FIXME: This is just an example.
test_jobs = SimpleTestJobDesign(jigdo_config, template_slices, file_name)

if building_images:
    # don't use for image, because it overwrites namespace.
    #for image in jigdo_config.Images.keys():
    for selected_image in jigdo_config.Images.keys():
        if str(selected_image) in active_images:
            iso = jigdo_config.Images[selected_image]
            # FIXME: Support all [Image] metadata
            test_jobs.initISO(iso["Template-MD5Sum"], iso["Template"], iso["Filename"])

    test_jobs.getISOslices()
    for directory in jigdo_config.scan_dirs:
        test_jobs.scan_dir(directory)
    for iso_image_file in jigdo_config.scan_isos:
        iso_image_file.mount()
        test_jobs.scan_dir(iso_image_file.location)
        iso_image_file.umount()
    """for iso_image in test_jobs.images:
            ## Ok, we have iso_image which is an ISOImage object ready to go. Just an example.
            ## We would want this to go into a queue and be blown away by threads ;-)
            print "Downloading needed slices for %s..." % iso_image.location
            num_download = len(iso_image.image_slices.keys()) + 1
            for num, image_slice in enumerate(iso_image.image_slices.iterkeys()):
                print iso_image.image_slices[image_slice]"""
    # ^ = all false... so it's after here
    # This is actually doing what it's supposed to do.
    # It checks and updates our python objects based on what all our scan_dir() calls were able to do.
    test_jobs.checkISOslices()
    # At this point, we should be ready to just download what the scan_dir() calls could not find.

    test_jobs.run(options.download_threads)

    for isoimage in test_jobs.images:
        print "Image defined by template %s is located %s" % (isoimage.template, isoimage.location)
        print "Checking if sums match..."
        if isoimage.checkImage():
            print "Sums match. Image %s is complete." % isoimage.location
            isoimage.finished = True
        else:
            print "Sums don't match. Image %s is not complete." % isoimage.location
            isoimage.finished = False

if hosting_images:
    # FIXME: Make it so this will actually scan stuff.
    for directory in jigdo_config.scan_dirs:
        print "Not able to scan % yet. Sorry." % directory
    for iso_image_file in jigdo_config.scan_isos:
        print "Not able to scan % yet. Sorry." % iso_image_file.location

    # FIXME: Support only hosting specific images (based on templates)
    # This just downloads what matches the selected server ids.
    num_slices = len(template_slices.slices)
    counter = 0
    for image_slice_sum in template_slices.slices:
        counter += 1
        image_slice_object = template_slices.slices[image_slice_sum]
        if image_slice_object.server_id in mirror_server_ids:
            while not image.download_slice(image_slice_object.slice_sum, counter, num_slices, 
                                           jigdo_config, template_slices, file_name,
                                           local_dir=options.host_data_directory):
                # Cheap hack to make it run until ^ works
                pass
        else:
            print "[%s/%s] %s not found via selected server id(s), not downloading..." % (counter, num_slices, image_slice_object.file_name)
    print "\nAll found files downloaded to %s." % options.host_directory

