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
# the Free Software Foundation; version 2 only
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
import re
import time
from ConfigParser import ConfigParser
import distutils, distutils.sysconfig
from urlgrabber import urlgrab
from urlgrabber.grabber import URLGrabError
from urlgrabber.progress import TextMeter
from urlparse import urlparse
from urlparse import urljoin
from urlgrabber import urlread
import types
import subprocess
from rhpl.translate import _, N_
import rhpl.translate as translate
import base64
import select

try:
    # new versions of python. Use hashlib	
    import hashlib as md5_hashlib
except ImportError:
    # old versions of python. Use now deprecrated md5
    import md5 as md5_hashlib

import threading
import thread
import Queue
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
                 help="Number of public mirrors to try before using a fallback mirror. (Default: 5)")

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
                 help="Directory to download data to.")

#
## Generation Options
## Purpose: Allow a user to generate jigdo configs and templates.
## FIXME: Move code from jigdo.py to here.
generation_group = parser.add_option_group(_("Generation Options"))

# Parse Options
(options,args) = parser.parse_args()

# Setup all of our classes. This will be moved, but just stick them here:
### Classes ###

class CustomParser(ConfigParser):
    """ Custom class to make sure we preserve case. """
    def optionxform(self, option):
        return str(option)

class ImageSlice:
    """ A file needing to be downloaded for an image. """
    def __init__(self, md5_sum, mirrors, file_name, server_id):
        """ Initialize the ImageSlice """
        self.location = ""
        self.finished = False
        self.slice_sum = md5_sum
        self.file_name = file_name
        self.server_id = server_id
        self.sources = self.getSources(file_name, mirrors)

    def getSources(self, file_name, mirrors):
        """ Return a list of SliceSource objects. """
        source_list = []
        source_list.append(SliceSource(file_name, mirrors))
        return source_list

class TemplateSlices:
    """ Hold all our slice objects. """
    def __init__(self, jigdo_config, slice_dict):
        """ Init our slices object. """
        self.slices = {}
        print "Generating slices defined in jigdo..."
        self.generate_slices(jigdo_config, slice_dict)

    def generate_slices(self, jigdo_config, slice_dict):
        """ Create ImageSlice objects that can be referenced from an ISOImage object. """
        for template_slice in slice_dict.keys():
            data = slice_dict[template_slice]
            server, file_name = data.split(':' ,1)
            mirrors = {}
            for type in ('geo', 'global', 'fallback'):
                mirrors[type] = [m[1]
                    for m in getattr(jigdo_config, 'mirror_%s' % type)
                        .itervalues()
                    if m[0] == server]
            self.slices[template_slice] = ImageSlice(template_slice, mirrors, file_name, server)


class SliceSource:
    """ A list of full urls for a source. This is compiled from taking the mirror list or
    mirror selection and building valid urls for the given file."""
    def __init__(self, file_name, mirrorlist):
        """ Init our slice source. """
        self.geo_urls = {}
        self.global_urls = {}
        self.fallback_urls = {}
        self.build_urls(mirrorlist, file_name)

    def build_urls(self, mirrorlist, file_name):
        """ Build urls from our file name and mirrorlist. """
        if mirrorlist == None:
            return
        for list_type in mirrorlist.keys():
            # Set the url status to 0. The key value will be updated with the
            # HTTP Status code.
            for url in mirrorlist[list_type]:
                url = urljoin(url, file_name)
                already_added = False
                if list_type == "geo":
                    self.geo_urls[url] = "0"
                elif list_type == "global" and url not in self.geo_urls:
                        self.global_urls[url] = "0"
                elif (list_type == "fallback" and url not in self.geo_urls
                        and url not in self.global_urls):
                        self.fallback_urls[url] = "0"
                        
class ISOImage:
    """ An ISO image we are going to attempt to assemble. """
    def __init__(self, template, template_sum, location):
        self.image_slices = {}
        self.template = template
        self.template_sum = template_sum
        self.image_sum = ""
        self.finished = False
        self.location = location
        self.download = False

    def addSlices(self, slice_list):
        """ Add the given md5 sums to the list of files needed by this ISO image. """
        for image_slice_md5 in slice_list:
            self.image_slices[image_slice_md5] = False

    def downloadSlice(self, slice_md5, current_num, num_download):
        """ Find the SliceObject, download it if needed, and then mark as done. """
        download_slice(slice_md5, current_num, num_download, iso_image=self)

    def checkImage(self):
        """ Check to make sure all needed files have been downloaded. """
        #for image_slice in self.image_slices:
        #    if not image_slice: return False
        if options.debug: print "Checking Image %s against sum %s" % (self.location, self.image_sum)
        if not compare_sum(self.location, self.image_sum):
            return False
        return True

    def getSlices(self):
        """ Read image template, gather needed slice information and add it to the object. """
        slices = []
        template_data = run_command(["jigdo-file", "ls", "--template", self.template], inshell=True)
        slices = [line.split()[3] for line in template_data
            if line.startswith('need-file')]
        if options.debug: print "Getting slices for %s... got %s slices" % (self.template, len(slices))
        self.addSlices(slices)

    def getImageSum(self):
        """ Read image template, get the image sum. """
        template_data = run_command(["jigdo-file", "ls", "--template", self.template], inshell=True)
        md5_sum = [line.split()[2] for line in template_data
            if line.startswith('image-info')]
        print template_data
        if options.debug: print "Image %s's sum is reported as %s..." % (self.location, md5_sum)
        self.image_sum = md5_sum

    def checkSlices(self):
        """ Check what slices have been merged into the image, and update the slice status. """
        template_tmp_file = self.location + ".tmp"
        if not os.path.isfile(template_tmp_file):
            if self.checkImage():
                for slice_md5 in self.image_slices:
                    template_slices.slices[slice_md5].finished = True
                    self.image_slices[slice_md5] = True
            else:
                return True
        template_data = run_command(["jigdo-file", "ls", "--template", template_tmp_file], inshell=True)
        slices = [line.split()[3] for line in template_data
            if line.startswith('have-file')]
        for slice_md5 in slices:
            if slice_md5 in template_slices.slices:
                template_slices.slices[slice_md5].finished = True
                self.image_slices[slice_md5] = True
        return True

class jigdoDefinition:
    """ The Jigsaw definition file """
    def __init__(self, definition_file_loc, mirror_file_loc):
        """ Let's init the configuration.
            @param definition_file_loc: Definition file location
            @param mirror_file_loc: Mirror file location"""
        self.definition_file_loc = definition_file_loc
        self.parser = CustomParser()
        self.__allSections = []
        self.cache_dir = os.path.join(options.download_workdir, "cache")
        self.cache_db = os.path.join(self.cache_dir, "jigdo-cache.db")
        self.mirror_geo = {}
        self.mirror_global = {}
        self.mirror_fallback = {}
        self.mirror_preferred = {}
        self.mirror_num = 0
        self.jigdo_url = ""
        self.scan_dirs = []
        self.scan_isos = []
        print "Reading jigdo configuration..."
        self.parse()
        
    def parse(self):
        """ Do the actual parsing """
        self.definition_file = open(self.definition_file_loc, 'r')
        self.parser.readfp(self.definition_file)
        # readfp seeks to end - Reset file
        self.definition_file.seek(0)
        toSearch = re.compile('(\n\[Image\].*\[)', re.DOTALL)
        content = self.definition_file.read()
        if not content:
            print 'You have supplied an emtpy file, valid jigsaw definition required.'
            return False
        matches = re.search(toSearch, content)
        matchedString = matches.string[matches.span()[0]+1:matches.span()[1]-1]
        # we want this here because we clear all other variables; Images should
        # be too (incase we reparse)
        self.Images = {}
        counter = 0
        for match in matchedString.split('[Image]'): # for each image section
            image = {}
            for line in match.strip('\n').split('\n'): # for each line in it
                if len(line.split('=')) == 2:
                    key, value = line.split('=')
                    image[key] = value
                else:
                  #if options.debug: print 'DEBUG: length: %i line: %s' % (len(line), line)
                  continue
            self.Images[counter] = image
            counter += 1
        self.Images.pop(0) # remove the empty set
        del(counter)
        for section in self.parser.sections():
            if section.lower() == 'image':
                # uh-oh. There are multiple [Image] sections -- No good for
                # ConfigParser, we'll have to do some good old-fashioned re.
                self.__allSections.append(['Images', self.Images])
                continue
            # this makes a self.section for each section
            # FIXME: Check all valid sections exist in sections()
            setattr(self, section, {})
            for option in self.parser.options(section):
                #if section in ("Servers", "Mirrorlists"):
                    # FIXME: This just creates a one item list. Blah. We need all the
                    #        items but I needed the list data type. For now, this forces
                    #        the data type we need.
                    #s = getattr(self, section)
                    #if option not in s:
                    #	s[option] = []
                    #s[option].append(self.parser.get(section, option))
                    #getattr(self, section)[option] = list(self.parser.get(section, option))
                #else:
                    # this makes a dict of {'Key', 'Value} from the parser
                    getattr(self, section)[option] = self.parser.get(section, option)
            self.__allSections.append([section, getattr(self, section)])
        self.definition_file.close()
        return True
        
    def getSections(self):
        """ Return all sections used from the config """
        return self.__allSections
        
    def buildMirrors(self):
        """ Fetch full URLS from our mirror list and populate. """
        mirror_id = 1
        for server_id in self.Servers.keys():
            self.mirror_fallback[mirror_id] = [server_id, self.Servers[server_id]]
            mirror_id += 1
        try:
            for server_id in self.Mirrorlists.keys():
                try:
                    data = urlread(self.Mirrorlists[server_id]).splitlines()
                    global_data = urlread("%s&country=global" % self.Mirrorlists[server_id]).splitlines()
                    for data_item in data:
                        if not re.compile("#").search(data_item):
                            self.mirror_geo[mirror_id] = [server_id, data_item + "/"]
                            mirror_id += 1
                    for data_item in global_data:
                        if not (re.compile("#").search(data_item)) and not (data_item in data):
                            self.mirror_global[mirror_id] = [server_id, data_item + "/"]
                            mirror_id += 1
                except URLGrabError:
                    print "Failed fetching mirror list from %s not adding mirrors from this source..." % self.Mirrorlists[server_id]
        except AttributeError:
            print "No mirror lists defined, not building mirror lists."
        self.mirror_num = mirror_id - 1



# FIXME: This is nothing but a test for working with the objects we have so far.
# We will want to subclass the pool.py
class SimpleTestJobDesign:
    """ This is just a test class for building our objects and looping them. """
    def __init__(self, jigdo_config):
        """ Get our storage setup. """
        self.images = []
        self.jigdo_config = jigdo_config
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
        check_directory(jigdo_config.cache_dir)
        for iso_image in self.images:
            ## Ok, we have iso_image which is an ISOImage object ready to go. Just an example.
            ## We would want this to go into a queue and be blown away by threads ;-)
            print "Downloading needed slices for %s..." % iso_image.location
            num_download = len(iso_image.image_slices.keys()) + 1
            for num, image_slice in enumerate(iso_image.image_slices.iterkeys()):
                if not iso_image.image_slices[image_slice]:
                    iso_image.downloadSlice(image_slice, num+1, num_download)

        # FIXME: Put it all together
        # We need to run some checks to make sure we have all the slices, maybe md5sum
        # checking, but jigdo will do this on its own. We should maybe only check sums
        # after we feed the downloaded data to jigdo, it rejects it and we want to check
        # for ourselves. The md5 infrastructure is here for when we start moving away from
        # jigdo-file for actually putting things back together.
        
        # Have jigdo-file start stuffing data where it needs to go.
        self.scan_dir(jigdo_config.cache_dir)
        
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
            local_template = os.path.join(options.download_workdir, "images", template)
            iso_location = os.path.join(options.download_workdir, "images", file_name)
            check_directory(os.path.dirname(local_template))
            check_directory(os.path.dirname(iso_location))
            template_local = False
            if os.path.isfile(local_template):
                print "Template %s exists, checking if complete..." % local_template
                if compare_sum(local_template, template_md5):
                    print "Template is complete."
                    template_local = True
                else:
                    print "Template is not complete..."
            if not template_local:
                print "Fetching template %s" % template_url
                urlgrab(template_url, filename=local_template, progress_obj=TextMeter())
            isoimage = ISOImage(local_template, template_md5, iso_location)
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
            iso_image.checkSlices()

    def scan_dir(self, directory):
        """ Scan a directory for local files that wont need to be downloaded. """
        # FIME: We might be able to scan for all active templates at one time,
        # otherwise we end up with more I/O from md5 checking then we would prefer.
        for iso_image in self.images:
            check_directory(os.path.dirname(iso_image.location))
            print "Scanning directory %s for files needed by %s..." % (directory, iso_image.location)
            # FIXME: Try to guess how long, maybe make a task list, or even better pipe the output
            # from the jigdo-lite command somewhere.
            print "This is going to take some time, please wait..."
            run_command(["jigdo-file", "make-image",
                        "--cache", jigdo_config.cache_db,
                        "--image", iso_image.location,
                        "--jigdo", jigdo_config.definition_file_loc,
                        "--template", iso_image.template,
                        "-r", "quiet",
                        "--force",
                        directory],
                        inshell=True)

class LoopbackMount:
    def __init__(self, lofile, mountdir, fstype = None):
        self.lofile = lofile
        self.mountdir = mountdir
        self.fstype = fstype

        self.mounted = False
        self.losetup = False
        self.rmdir   = False
        self.loopdev = None

    def cleanup(self):
        self.umount()
        self.lounsetup()

    def umount(self):
        if self.mounted:
            rc = subprocess.call(["/bin/umount", self.mountdir])
            self.mounted = False

        if self.rmdir:
            try:
                os.rmdir(self.mountdir)
            except OSError, e:
                pass
            self.rmdir = False

    def lounsetup(self):
        if self.losetup:
            rc = subprocess.call(["/sbin/losetup", "-d", self.loopdev])
            self.losetup = False
            self.loopdev = None

    def loopsetup(self):
        if self.losetup:
            return

        rc = subprocess.call(["/sbin/losetup", "-f", self.lofile])
        if rc != 0:
            raise MountError(_("Failed to allocate loop device for '%s'") % self.lofile)

        # succeeded; figure out which loopdevice we're using
        buf = subprocess.Popen(["/sbin/losetup", "-a"],
                               stdout=subprocess.PIPE).communicate()[0]
        for line in buf.split("\n"):
            # loopdev: fdinfo (filename)
            fields = line.split()
            if len(fields) != 3:
                continue
            if fields[2] == "(%s)" %(self.lofile,):
                self.loopdev = fields[0][:-1]
                break

        if not self.loopdev:
            raise MountError(_("Failed to find loop device associated with '%s' from '/sbin/losetup -a'") % self.lofile)

        self.losetup = True

    def mount(self):
        if self.mounted:
            return

        self.loopsetup()

        if not os.path.isdir(self.mountdir):
            os.makedirs(self.mountdir)
            self.rmdir = True

        args = [ "/bin/mount", self.loopdev, self.mountdir ]
        if self.fstype:
            args.extend(["-t", self.fstype])

        rc = subprocess.call(args)
        if rc != 0:
            raise MountError(_("Failed to mount '%s' to '%s'") % (self.loopdev, self.mountdir))

        self.mounted = True

class MountError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

### End Classes ###

### Global Functions ###

def run_command(command, rundir=None, inshell=False, env=None, stdout=subprocess.PIPE, show=False):
    """ Run a command and return output. """

    if rundir == None:
        rundir = options.download_workdir

    check_directory(rundir)

    ret = []
    p = subprocess.Popen(command, cwd=rundir, stdout=stdout, stderr=subprocess.STDOUT, shell=False)
    while p.poll() == None:
      for item in p.stdout.read().split('\n'):
        ret.append(item)
      time.sleep(0.01)
    for item in p.stdout.read().split('\n'):
      ret.append(item)
    p.stdout.close()
    if options.debug: print "\n==== %s Output ====\n%s\n==== End Output ====\n" % (' '.join(command), '\n'.join(ret))
    return ret

#    p = subprocess.Popen(command, cwd=rundir, stdout=stdout, stderr=subprocess.STDOUT, shell=inshell, bufsize=1)
#'''    ret = []
#    while True:
#    	s = select.select([p.stdout], [], [], 0.001)
#    	if len(s[0]) > 0:
#    		line = p.stdout.readline()
#    		if show:
#    			sys.stdout.write(line)
#    		ret.append(line)
#	if p.poll() != None:
#    		break'''
#    ret = p.communicate()[0].split('\n')
#    p.stdout.close()
#    return ret


def download_slice(slice_md5, current_num, num_download, iso_image=None, local_dir=None):
    """ Download the given slice. """
    remaining_tries = options.fallback_number
    slice_object = template_slices.slices[slice_md5]
    local_location = os.path.join(jigdo_config.cache_dir, slice_object.file_name)
    if local_dir:
        local_location = os.path.join(local_dir, slice_object.file_name)
    storage_path = os.path.dirname(local_location)
    check_directory(storage_path)
    if os.path.isfile(local_location):
        if compare_sum(local_location, slice_object.slice_sum):
            print "[%s/%s] %s is complete, skipping." % (current_num, num_download, local_location)
            if iso_image: iso_image.image_slices[slice_md5] = True
            slice_object.finished = True
            slice_object.location = local_location
            return
    for source in jigdo_config.mirror_preferred:
        mirror_data = jigdo_config.mirror_preferred[source]
        if not slice_object.server_id == mirror_data[0]: continue
        url = urljoin(mirror_data[1], file_name)
        try:
            print "[%s/%s] Trying to download %s: \n\t --> %s" % (current_num, num_download, url, local_location)
            urlgrab(url, filename=local_location, progress_obj=TextMeter())
            if iso_image: iso_image.image_slices[slice_md5] = True
            slice_object.finished = True
            slice_object.location = local_location
            source.fallback_urls[url] = "200"
            break
        except URLGrabError:
            print "Failed downloading %s (will try backup urls later)..." % url
            pass
    download_found = False
    for source in slice_object.sources:
        slice_object_finished = False
        iso_image_status = False
        if not slice_object.finished:
            slice_object_finished = True
        if iso_image:
            iso_image_status = iso_image.image_slices[slice_md5]
        if slice_object_finished and not iso_image_status:
            for url in source.geo_urls.keys():
                if source.geo_urls[url] != "404" and not download_found and remaining_tries > 0:
                    try:
                        print "[%s/%s] Trying to download %s: \n\t --> %s" % (current_num, num_download, url, local_location)
                        urlgrab(url, filename=local_location, progress_obj=TextMeter())
                        download_found = True
                        break
                    except (URLGrabError, KeyboardInterrupt):
                        source.geo_urls[url] = "404"
                        remaining_tries -= 1
            for url in source.global_urls.keys():
                if source.global_urls[url] != "404" and not download_found and remaining_tries > 0:
                    try:
                        print "[%s/%s] Trying to download %s: \n\t --> %s" % (current_num, num_download, url, local_location)
                        urlgrab(url, filename=local_location, progress_obj=TextMeter())
                        download_found = True
                        break
                    except (URLGrabError, KeyboardInterrupt):
                        source.global_urls[url] = "404"
                        remaining_tries -= 1
            for url in source.fallback_urls.keys():
                if source.fallback_urls[url] != "404" and not download_found:
                    try:
                        print "[%s/%s] Trying to download %s: \n\t --> %s" % (current_num, num_download, url, local_location)
                        urlgrab(url, filename=local_location, progress_obj=TextMeter())
                        download_found = True
                        break
                    except (URLGrabError, KeyboardInterrupt):
                        source.fallback_urls[url] = "404"
        else:
            break
        if download_found:
            if iso_image: iso_image.image_slices[slice_md5] = True
            slice_object.finished = True
            slice_object.location = local_location
            break


def check_directory(directory):
    """ Check if directory exists. If not, create it or fail. """
    if not os.access(directory, os.R_OK):
        try:
            os.makedirs(directory)
        except:
            print _("Directory %s could not be created. Aborting" % directory)
            sys.exit(1)

def compare_sum(target, base64_sum):
    """ Compares a file's sum to given sum. """
    B, K, M, G = 1, 1024, 1024*1024, 1024*1024*1024
    # now that our sizes are defined let's do some multiplication
    bufsize = 8*K*B
    mode = 'rb'
    if not os.path.isfile(target): return False
    f = open(target, mode)
    md5 = md5_hashlib.md5()
    try:
        while True: # this just reads to the end and updates the hash
            temp_data = f.read(bufsize)
            if not temp_data:
                f.close()
                break
            md5.update(temp_data)
    except Exception, error_description:
        # eventually let's actually do something here when it fails
        print 'An error occurred while running checksum: %s' % error_description
        return False
    calc = md5.digest()
    base64_calc = base64.urlsafe_b64encode(calc)
    eq = re.compile('=')
    base64_strip = eq.sub('', base64_calc)
    if options.debug: "Checking %s against %s..." % (base64_strip, base64_sum)
    if base64_strip == base64_sum:
        return True
    else:
        return False

def sortDictValues(adict):
    keys = adict.keys()
    keys.sort()
    return map(adict.get, keys)

def printOut(dictionary, loop):
    """ Print out a dict """
    addStr = '\t'
    endStr = '--> '
    fullLoopStr = addStr
    for number in range(loop):
        fullLoopStr += addStr
    fullLoopStr += endStr
    for key, value in dictionary.iteritems():
        if type(key) == types.DictType: # loop
            printOut(key, loop+1)
        elif type(value) == types.DictType:
            print '%s%s:' % (fullLoopStr, key)
            printOut(value, loop+1)
        else:
            print '%s%s:\t%s' % (fullLoopStr, key, value)

### End Global Functions ####

# Check options

building_images = False
hosting_images = False

## FIXME: Here we want to check if we are given enough information by the user,
## or if we are going to need to go interactive to answer more questions.

## FIXME: We most like want this info to go into some sort of config object.

if options.base_download_mirror or options.updates_download_mirror:
    print "\n\tSelecting mirrors via options is not supported yet. Sorry.\n"
    sys.exit(1)

if options.host_image_numbers:
    print "\n\tSelecting images via options is not supported yet. Sorry.\n"
    sys.exit(1)

if options.host_all and (options.host_directory == ""):
    print "\n\tYou must select a location to host the data defined in this jigdo. Use --host-dir\n"
    sys.exit(1)

if (options.host_image_numbers or options.host_all or (options.host_directory != "")) and (options.download_image_numbers or options.download_all):
    print "\n\tYou can not download and setup hosting at the same time yet. Sorry.\n"
    sys.exit(1)

if options.download_image_numbers or options.download_all:
    building_images = True

if options.host_image_numbers or options.host_all:
    hosting_images = True



# Make download_workdir absolute
download_workdir = os.path.abspath(options.download_workdir)
check_directory(download_workdir)
options.download_workdir = download_workdir

user_specified_images = False
jigdo_file = ""
if options.jigdo_source == "":
    print "\n\tNo jigdo file specified. Use --jigdo\n"
    sys.exit(1)
else:
    print "Fetching %s..." % options.jigdo_source
    try:
        file_name = os.path.basename(urlparse(options.jigdo_source).path)
    except AttributeError:
        file_name = options.jigdo_source
    jigdo_local_file = os.path.join(options.download_workdir, file_name)
    try:
        jigdo_source = urlgrab(options.jigdo_source, filename=jigdo_local_file,
        	progress_obj=TextMeter())
    except URLGrabError:
        print "Unable to fetch %s" % options.jigdo_source
        sys.exit(1)
    jigdo_file = jigdo_source

# Init our jigdo_config
# eventually None ==> external mirror list file that we want to merge
jigdo_config = jigdoDefinition(jigdo_file, None)
jigdo_config.jigdo_url = options.jigdo_source

if options.show_info_exit:
    """ Show the user what we know about the jigdo template, and then exit."""
    # the layout for the jigdoDefinition is the same as the config file
    # self.SectionName['OptionName'] retrieves a value
    for section in jigdo_config.getSections():
        print '** %s:' % section[0]
        printOut(section[1], 0)
        #print section[1]
    sys.exit(1)

if options.download_image_numbers or options.host_image_numbers:
    user_specified_images = True

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
    while adding_scan_dirs:
        scan_question = raw_input("Would you like to scan any directories for needed files? [y/N] ")
        if scan_question.lower() not in ["y", "yes"]: break
        scan_directory = raw_input("What directory would you like to scan? ")
        full_path = os.path.abspath(scan_directory)
        if not os.access(full_path, os.R_OK):
            print "Directory %s not accessable, will not scan." % full_path
        else:
            jigdo_config.scan_dirs.append(full_path)
        if len(jigdo_config.scan_dirs) > 0: print "Currently going to scan directories: %s" % ", ".join(jigdo_config.scan_dirs)
        scan_add_more = raw_input("Would you like to add another directory to scan? [y/N] ")
        if scan_add_more.lower() not in ["y", "yes"]: adding_scan_dirs = False

if options.scan_isos:
    for iso_file in options.scan_isos:
        full_path = os.path.abspath(iso_file)
        if not os.access(full_path, os.R_OK):
            print "ISO image %s not accessable, will not scan." % full_path
        else:
            jigdo_config.scan_isos.append(LoopbackMount(full_path,
                                          os.path.join(options.download_workdir, "mounts", os.path.basename(full_path)),
                                          "iso9660"))
    print "These ISO images will be scanned before downloading any files:"
    for iso_file in jigdo_config.scan_isos:
        print "\t%s" % iso_file["iso"]
else:
    adding_iso_images = True
    while adding_iso_images:
        scan_question = raw_input("Would you like to scan any iso images for needed files? [y/N] ")
        if scan_question.lower() not in ["y", "yes"]: break
        scan_directory = raw_input("What ISO image would you like to scan? ")
        full_path = os.path.abspath(scan_directory)
        if not os.access(full_path, os.R_OK):
            print "ISO image %s not accessable, will not scan." % full_path
        else:
            jigdo_config.scan_isos.append(LoopbackMount(full_path,
                                          os.path.join(options.download_workdir, "mounts", os.path.basename(full_path)),
                                          "iso9660"))
        if len(jigdo_config.scan_isos) > 0:
            print "These ISO images will be scanned before downloading any files:"
            for iso_file in jigdo_config.scan_isos:
                print "\t%s" % iso_file["iso"]
        scan_add_more = raw_input("Would you like to add another ISO image to scan? [y/N] ")
        if scan_add_more.lower() not in ["y", "yes"]: adding_iso_images = False

# Ask the user what images they want to download
# FIXME: So, this is where we start the interactive process. If they have not defined
# what|where to download, we need to ask them.

active_images = []
if not user_specified_images and not options.download_all and not options.host_all:
    choosing_images = True
    while choosing_images:
        printOut(jigdo_config.Images, 0)
        num_images = len(jigdo_config.Images)
        image_choice = raw_input("What image would you like to download? [1-%s] " % num_images )
        if image_choice == "":
            print "No images selected for download. Exiting."
            sys.exit(1)
        if int(image_choice) > num_images:
            print "Image not found."
        elif image_choice not in active_images:
            active_images.append(image_choice)
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
    for image in jigdo_config.Images:
        active_images.append(image)
elif user_specified_images:
    print "Adding selected images to download..."
    for image in (options.download_image_numbers + options.host_image_numbers):
        if int(image) in jigdo_config.Images:
            active_images.append(image)
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
        server_choice = raw_input("\nWhat server ID would you like to download? [1-%s] (Default: All) " % num_servers )
        if server_choice == "":
            for sid in server_ids:
                mirror_server_ids.append(server_ids[sid])
        elif int(server_choice) > num_servers:
            print "Source not found."
        elif server_ids[server_choice] not in mirror_server_ids:
            mirror_server_ids.append(server_ids[server_choice])
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
    # FIXME: This needs some magic. I think just pushing these into the front of our
    # geo mirrorlist would be best. The we at least still offer the user a preference
    # selection while preserving a fallback if the selected mirror is incomplete
    pass
else:
    if len(jigdo_config.mirror_fallback.keys()) > 0: print "\nJigdo Provided Mirror Sources:\n"
    for mirror in jigdo_config.mirror_fallback.keys():
       print "\t%s: '%s' - %s" % (mirror, jigdo_config.mirror_fallback[mirror][0], jigdo_config.mirror_fallback[mirror][1])

    if len(jigdo_config.mirror_geo.keys()) > 0: print "\nGeoIP Based Mirrors (from mirror list):\n"
    for mirror in jigdo_config.mirror_geo.keys():
       print "\t%s: '%s' - %s" % (mirror, jigdo_config.mirror_geo[mirror][0], jigdo_config.mirror_geo[mirror][1])

    if len(jigdo_config.mirror_global.keys()) > 0: print "\nGlobal Mirrors (from mirror list):\n"
    for mirror in jigdo_config.mirror_global.keys():
       print "\t%s: '%s' - %s" % (mirror, jigdo_config.mirror_global[mirror][0], jigdo_config.mirror_global[mirror][1])

    user_chose_mirrors = raw_input("\nWould you like to select a specific mirror to download from? (Default: Use all, closest first) [y/N] ")
    if user_chose_mirrors.lower() in ["y", "yes"]:
        choosing_mirrors = True
        while choosing_mirrors:
            mirror_choice = raw_input("What mirror would you like to use? [1-%s] " % jigdo_config.mirror_num)
            if int(mirror_choice) > jigdo_config.mirror_num:
                print "Invalid mirror number."
            elif mirror_choice not in preferred_mirrors:
                preferred_mirrors.append(mirror_choice)
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
template_slices = TemplateSlices(jigdo_config, jigdo_config.Parts)


# FIXME: This is just an example.
test_jobs = SimpleTestJobDesign(jigdo_config)

if building_images:
    for image in jigdo_config.Images.keys():
        if str(image) in active_images:
            iso = jigdo_config.Images[image]
            # FIXME: Support all [Image] metadata
            test_jobs.initISO(iso["Template-MD5Sum"], iso["Template"], iso["Filename"])

    test_jobs.getISOslices()
    for directory in jigdo_config.scan_dirs:
        test_jobs.scan_dir(directory)
    for iso_image_file in jigdo_config.scan_isos:
        iso_image_file.mount()
        test_jobs.scan_dir(iso_image_file.location)
        iso_image_file.umount()
    test_jobs.checkISOslices()

    test_jobs.run(options.download_threads)

    for isoimage in test_jobs.images:
        print "Image defined by template %s is located %s" % (isoimage.template, isoimage.location)
        print "Checking if sums match..."
        isoimage.getImageSum()
        if isoimage.checkImage():
            print "Sums match. Image is complete."
        else:
            print "Sums don't match. Image is not complete."

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
            download_slice(image_slice_object.slice_sum, counter, num_slices, local_dir=options.host_directory)
        else:
            print "[%s/%s] %s not found via selected server id(s), not downloading..." % (counter, num_slices, image_slice_object.file_name)
    print "\nAll found files downloaded to %s." % options.host_directory

print "\nThanks for using the alpha version of pyjigdo.\n"








