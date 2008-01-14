#
# Copyright 2007, 2008 Fedora Unity
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
Code dealing with interactions with Jigdo commands
"""

import os
from urlgrabber import urlgrab
from urlgrabber.grabber import URLGrabError
from urlgrabber.progress import TextMeter
from urlparse import urlparse
from urlparse import urljoin
from urlgrabber import urlread

class JigdoJobPool:
    """ This is just a test class for building our objects and looping them. """
    def __init__(self, jigdo_config, template_slices, file_name):
        """ Get our storage setup. """
        self.images = []
        self.jigdo_config = jigdo_config
        self.template_slices = template_slices
        self.file_name = file_name
        self.clearCache()

    def clearCache(self):
        """ Delete any files needing to be cleared from any previous run."""
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
            if hosting_images:
                local_template = os.path.join(options.host_templates_directory, "%s.template" % file_name)
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
                urlgrab(template_url, filename=local_template, progress_obj=TextMeter(), timeout=options.urlgrab_timeout)
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

class JigdoRepoDefinition:
    """ A repo definition that has a mapping to all needed bits for a label to be defined. """
    def ___init___(self, data_source, label, baseurl=None, mirrorlist=None):
        self.data_source = data_source
        self.label = label
        self.baseurl = baseurl
        self.mirrorlist = mirrorlist


def generate_jigdo_template(jigdo_file_name, template_file_name, iso_image_file, repos, merge=False):
    """ Generate a .jigdo and .template """
    
    for repo in repos: 
        if not isinstance(repo, JigdoRepoDefinition): raise JigdoError, "Was given flawed repo data."
    
    if merge:
        if not os.access(jigdo_file_name, os.RW_OK):
            #FIXME: Design JigdoError
            #raise JigdoError, "Can not write to proposed jigdo file %s" % jigdo_file_name
            pass
    else:
        #FIXME: Don't shell out to touch, implement this in python
        init_jigdo_location_command = ["/bin/touch", "%s" % jigdo_file_name]
        misc.run_command(init_jigdo_location_command)

    generation_command_data_sources = []
    for repo in repos:
        generation_command_data_sources.extend(
        "%s/" % repo.data_source,
        "--label %s=%s" % (repo.label, repo.data_source))
    
    generation_command = [
        "/usr/bin/jigdo-file",
        "make-template",
        "--image=%s" % iso_image_file,
        "--jigdo=%s" % jigdo_file_name,
        "--template=%s" % os.path.join(options.generation_directory, iso_image_file + '.template'),
        "--no-servers-section",
        "--force"]
    if merge: generation_command.append("--merge=%s" % jigdo_file_name)
    generation_command.extend(generation_command_data_sources)
    
    misc.run_command(generation_command)
