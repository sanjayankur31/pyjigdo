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
Code dealing with the image, it's slices and templates.
"""

import os, os.path

from urlgrabber import urlgrab
from urlgrabber.grabber import URLGrabError
from urlgrabber.progress import TextMeter
from urlparse import urljoin

from interfaces import options
from misc import run_command, compare_sum, check_directory

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
            server, file_name = data.split(':', 1)
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

    def downloadSlice(self, slice_md5, current_num, num_download, jigdo_config, template_slices, file_name):
        """ Find the SliceObject, download it if needed, and then mark as done. """
        download_slice(slice_md5, current_num, num_download, jigdo_config, template_slices, file_name, iso_image=self)

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

    def checkSlices(self, template_slices):
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

def download_slice(slice_md5, current_num, num_download, jigdo_config, template_slices, file_name, iso_image=None, local_dir=None):
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


