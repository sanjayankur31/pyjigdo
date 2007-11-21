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
from urlparse import urlsplit

from interfaces import options
from misc import run_command, compare_sum, check_directory

import rhpl.translate as translate
from rhpl.translate import _, N_

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
        print _("Generating slices defined in jigdo...")
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
        self.getImageSum()
        if os.path.isfile(self.location):
            print _("Image %s is already present, checking if complete..." % self.location)
            if self.checkImage():
                print _("Image %s is complete, wont download." % self.location)
                self.finished = True
            else:
                print _("Image %s is not complete, will download." % self.location)

    def addSlices(self, slice_list):
        """ Add the given md5 sums to the list of files needed by this ISO image. """
        for image_slice_md5 in slice_list:
            self.image_slices[image_slice_md5] = False

    def downloadSlice(self, slice_md5, current_num, num_download, jigdo_config, template_slices, file_name):
        """ Call download_slice to get our slice for us. """
        return download_slice(slice_md5, current_num, num_download, jigdo_config, template_slices, file_name, iso_image=self)

    def checkImage(self):
        """ Check to see if image is built. """
        if options.debug:
            print _("Checking Image %s against sum %s" % (self.location, self.image_sum))
        if not compare_sum(self.location, self.image_sum):
            return False
        return True

    def getSlices(self):
        """ Read image template, gather needed slice information and add it to the object. """
        slices = []
        template_data = run_command(["jigdo-file", "ls", "--template", self.template], inshell=True)
        slices = [line.split()[3] for line in template_data
            if line.startswith('need-file')]
        if options.debug: print _("Getting slices for %s... got %s slices" % (self.template, len(slices)))
        self.addSlices(slices)

    def getImageSum(self):
        """ Read image template, get the image sum. """
        template_data = run_command(["jigdo-file", "ls", "--template", self.template], inshell=True)
        md5_sum = [line.split()[2] for line in template_data
            if line.startswith('image-info')]
        if options.debug: print _("Image %s's sum is reported as %s..." % (self.location, md5_sum[0]))
        self.image_sum = md5_sum[0]

    def checkSlices(self, template_slices):
        """ Check what slices have been merged into the image, and update the slice status. """
        template_tmp_file = self.location + ".tmp"
        if not os.path.isfile(template_tmp_file):
            # The goal here was to have the logic, if we don't have a tmp file anymore, we must have been able to create the image
            # using all local data, let's check if that is the case:
            # FIXME: Don't assume self.location is a file if template_tmp_file is not. self.checkImage() would do this anyways, but
            # we run into the issue of template_slices.slices[slice_md5].finished = True again, though I'm not sure it's even an issue.
            # For now, i've just commented it out with a printed warning the image is done, rather then mathmatically checking.
            #if self.checkImage():
            #    for slice_md5 in self.image_slices:
            #        template_slices.slices[slice_md5].finished = True
            #        self.image_slices[slice_md5] = True
            #else:
            #    return True
            # This should only happen if our iso was sucessfully completed with the pre-download scans.
            if options.debug: print _("\n%s is not a file!? Does that mean %s is done?!\n" % (template_tmp_file, self.location))
        template_data = run_command(["jigdo-file", "ls", "--template", template_tmp_file], inshell=True)
        # This is supposed to filter us a list of files that the template is reporting as merged.
        # The "template" is template_tmp_file which is basically the iso in the making. It will report
        # have-file and need-file. We need to still download need-file and not download have-file.
	# Since our directory scans are what would have changed a slice to have-file we need to update
        # our python objects to state the files are downloaded. I do, now, see how  template_slices.slices[slice_md5].finished = True
        # might cause issues when downloading multiple images :-/ but our current use case is only downloading one.
        slices = [line.split()[3] for line in template_data
            # FIXME: What is this!?
            # This was added by ignacio. It should create an array of lines that start with have-file.. aka filter for lines that
            # are reported by the tmp iso image where the slice is in the state "have-file". This used to be template_data.splitlines()
            # and then regex match for lines that are "have-file", this seems more pythonfooish.. maybe it doesn't work as expected?
            if line.startswith('have-file')]
        if options.debug: print _("\n%s slices reported as downloaded: %s" % (len(slices), ", ".join(slices)) )
        slices_needed = [line.split()[3] for line in template_data
            if line.startswith('need-file')]
        if options.debug: print _("\n%s slices still needed: %s" % (len(slices_needed), ", ".join(slices_needed)) )
        for slice_md5 in slices:
            # Make sure we are not working on something that doesn't exist:
            if slice_md5 in template_slices.slices:
                # FIXME: Figure out how to gracefully tell all iso_image objects that we have a file downloaded. Problem being,
                # if a file was added to an image from a local location, we'll need to make sure it's available for all images.
                # (which it should be, because scan_dir is run for all iso_image objects...
                #template_slices.slices[slice_md5].finished = True
                # FIXME: This change is to just update the single iso_image object to be aware we don't need to download the files
                # the temp iso image already has (aka are marked "have-file")
                # Tell the downloader this slice is not needing to be downloaded, it was merged in during an earlier operation:
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
            print _("[%s/%s] %s is complete, skipping." % (current_num, num_download, local_location))
            if iso_image:
                iso_image.image_slices[slice_md5] = True
            slice_object.finished = True
            slice_object.location = local_location
            return True
        else:
            print _("[%s/%s] %s is incomplete, removing." % (current_num, num_download, local_location))
            if iso_image:
                iso_image.image_slices[slice_md5] = False
            slice_object.finished = False
            os.remove(local_location)
    for source in jigdo_config.mirror_preferred:
        mirror_data = jigdo_config.mirror_preferred[source]
        if not slice_object.server_id == mirror_data[0]: continue
        urldata = urlsplit(mirror_data[1])
        url = urljoin(mirror_data[1], file_name)
        if urldata.query:
            url = "%s://%s%s?%s/%s" % (urldata.scheme, urldata.netloc, urldata.path, urldata.query, file_name)
        try:
            print _("[%s/%s] Trying to download %s: \n\t --> %s" % (current_num, num_download, url, local_location))
            urlgrab(url, filename=local_location, progress_obj=TextMeter())
            # FIXME: Why do we compare the sum to determine a 404 error?
            # The sum needs to be compared due to 302s redirecting to incorrect data.
            if compare_sum(local_location, slice_object.slice_sum):
                if iso_image:
                    iso_image.image_slices[slice_md5] = True
                slice_object.finished = True
                slice_object.location = local_location
                source.fallback_urls[url] = "200"
                break
            else:
                source.fallback_urls[url] = "404"
        except URLGrabError:
            print _("Failed downloading %s (will try backup urls later)..." % url)
            source.fallback_urls[url] = "404"
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
                        print _("[%s/%s] Trying to download %s: \n\t --> %s" % (current_num, num_download, url, local_location))
                        urlgrab(url, filename=local_location, progress_obj=TextMeter())
                        if compare_sum(local_location, slice_object.slice_sum):
                            download_found = True
                            break
                        else:
                            source.geo_urls[url] = "404"
                            remaining_tries -= 1
                    except (URLGrabError, KeyboardInterrupt):
                        source.geo_urls[url] = "404"
                        remaining_tries -= 1
            for url in source.global_urls.keys():
                if source.global_urls[url] != "404" and not download_found and remaining_tries > 0:
                    try:
                        print _("[%s/%s] Trying to download %s: \n\t --> %s" % (current_num, num_download, url, local_location))
                        urlgrab(url, filename=local_location, progress_obj=TextMeter())
                        if compare_sum(local_location, slice_object.slice_sum):
                            download_found = True
                            break
                        else:
                            source.global_urls[url] = "404"
                            remaining_tries -= 1
                    except (URLGrabError, KeyboardInterrupt):
                        source.global_urls[url] = "404"
                        remaining_tries -= 1
            for url in source.fallback_urls.keys():
                if source.fallback_urls[url] != "404" and not download_found:
                    try:
                        print _("[%s/%s] Trying to download %s: \n\t --> %s" % (current_num, num_download, url, local_location))
                        urlgrab(url, filename=local_location, progress_obj=TextMeter())
                        if compare_sum(local_location, slice_object.slice_sum):
                            download_found = True
                            break
                        else:
                            source.fallback_urls[url] = "404"
                    except (URLGrabError, KeyboardInterrupt):
                        source.fallback_urls[url] = "404"
        else:
            break
        if download_found:
            if iso_image: iso_image.image_slices[slice_md5] = True
            slice_object.finished = True
            slice_object.location = local_location
            break
    if compare_sum(slice_object.location, slice_md5):
        if options.debug: print _('\t --> Checksum valid.')
        return True
    else:
        if options.debug: print _('\t --> Checksum INVALID!')
        # FIXME: Any calls to download_slice must be modified to restart a
        #        given slice when returning false
        if iso_image:
            iso_image.image_slices[slice_md5] = False
        slice_object.finished = False
        return False


