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
"""
Implementation of Jigdo concepts, calling jigdo-file when needed.
"""

import os, urlparse, sys, gzip
from ConfigParser import RawConfigParser

from pyJigdo.userinterface import SelectImages
from pyJigdo.util import url_to_file_name, check_complete

import pyJigdo.translate as translate
from pyJigdo.translate import _, N_

class JigdoFile:
    """ A Jigdo file that has been requested to be downloaded. """
    def __init__(self, log, async, settings, base, jigdo_location, jigdo_storage_location):
        self.log = log
        self.async = async
        self.settings = settings
        self.base = base
        self.jigdo_location = jigdo_location
        self.fs_location = jigdo_storage_location
        self.jigdo_data = None # JigdoDefinition()
        self.image_selection = None # SelectImages()
        self.id = jigdo_location
        self.has_data = False
        self.download_tries = 0

    def source(self):
        """ Return the source location for this jigdo file. """
        return self.jigdo_location

    def target(self):
        """ Return the target location for this jigdo file. """
        return self.fs_location

    def download_callback_success(self, ign):
        """ Callback entry point for when self.get() is successful. """
        self.download_tries += 1
        self.log.info(_("Successfully downloaded %s" % self.id))
        self.parse()
        if self.settings.list_images or self.settings.jigdo_info:
            # List Defined Images
            if self.settings.list_images: self.list_images()
            # Give all information we know back to the user:
            if self.settings.jigdo_info: self.full_info()
        else:
            self.select_images()
            self.get_templates()
        self.log.debug(_("Ending download event for %s" % self.id))

    def download_callback_failure(self, ign):
        """ Callback entry point for when self.get() fails. """
        self.download_tries += 1
        self.log.warning(_("Failed to download %s: \n\t%s" % ( self.id,
                                                             ign )))
        if self.download_tries >= self.settings.max_download_attempts:
            self.log.error(_("Max tries for %s reached. Not downloading." % self.id))
        else:
            self.async.request_download(self)
        self.log.debug(_("Failed download of %s, added new task to try again." % self.id))

    def queue_download(self):
        """ Queue the self.get() in the async. 
            We always need to re-fetch the jigdo file as we don't
            have a verified sum for the data. """
        self.async.request_download(self)

    def get(self):
        """ Download the Jigdo file using the async.
            Return the async task. """
        if self.download_tries >= self.settings.max_download_attempts:
            attempt = "last"
        else:
            attempt = self.download_tries + 1
        self.log.status(_("Adding a task to download: %s (attempt: %s)" % \
                       (self.id, attempt)))
        return self.async.download_object(self)

    def get_templates(self):
        """ Download the Jigdo file's defined templates that
            have been selected by the user. Here is where all
            the real magic starts. Don't get lost. """
        # These calls start their own event driven calls and
        # we now leave the first callback from the Jigdo file
        # download request.
        for jigdo_template in self.jigdo_data.images.values():
            if jigdo_template.selected:
                jigdo_template.queue_download()

    def select_images(self):
        """ Interact with the user to select what images we want. """
        self.image_selection = SelectImages( self.log,
                                             self.settings,
                                             self.base,
                                             self.jigdo_data )

    def parse(self):
        """ Parse the jigdo file. """
        if os.path.isfile(self.fs_location):
            self.log.debug(_("Successfully downloaded %s to %s" % ( self.id,
                                                                    self.fs_location )))
            self.log.debug(_("Attempting to parse %s ..." % self.id))
            self.jigdo_data = JigdoDefinition( self.async,
                                               self.log,
                                               self.settings,
                                               self.fs_location )

    def list_images(self):
        """ List the images defined in this Jigdo. """
        self.jigdo_data.list_images()

    def full_info(self):
        """ Print all information we know based on what we have
            downloaded so far. """
        self.jigdo_data.print_information()

class JigdoDefinition:
    """ A Jigdo Definition File.
        just_print is used to suppress the creation of objects. """
    def __init__(self, async, log, settings, file_name, just_print = False):
        self.async = async
        self.log = log
        self.settings = settings
        self.file_name = file_name
        self.image_unique_id = 0
        self.images = {}
        self.parts = None
        self.servers = None
        self.mirrors = None
        self.parse()
        if not just_print: self.create_objects()

    def list_images(self):
        """ Print the details about all images. """
        self.log.status(_("==== Images defined in Jigdo ===="))
        for (image_id, image) in self.images.iteritems():
            self.log.status(_("Image Number %s:\n%s" % (image_id, image)))

    def print_information(self):
        """ Print the contents of the definition. """
        self.log.status(_("==== Servers listed in Jigdo ===="))
        self.log.status(self.servers)
        self.log.status(_("==== Mirror list sources listed in Jigdo ===="))
        self.log.status(self.mirrors)
        self.log.status(_("==== Images defined in Jigdo ===="))
        for (image_id, image) in self.images.iteritems():
            self.log.status(_("Number %s:\n%s" % (image_id, image)))
        self.log.status(_("==== Parts defined in Jigdo ===="))
        self.log.status(self.parts)


    def parse(self):
        """ This parses the JigdoDefinition.file_name """
        cursect = None                            # None, or a dictionary
        optname = None
        lineno = 0
        e = None                                  # None, or an exception
        self._sections = []

        try:
            # If you try to read a non-gzip file with this class, it will throw an IOError
            fp = gzip.GzipFile(self.file_name, "rb")
            line = fp.readline()
            fp.rewind()
            self.log.debug(_("Jigdo file is Gzipped."))
        except IOError:
            fp = open(self.file_name,"r")
            
        while True:
            line = fp.readline()
            if not line:
                break
            # comment or blank line?
            if line.strip() in ('','\n') or line[0] in ('#', ';'):
                continue
            if line.split(None, 1)[0].lower() == 'rem' and line[0] in "rR":
                continue

            # no leading whitespace
            # continuation line?
            if line[0].isspace() and cursect is not None and optname:
                value = line.strip()
                if value:
                    cursect[optname] = "%s\n%s" % (cursect[optname], value)
            # a section header or option header?
            else:
                # is it a section header?
                mo = RawConfigParser.SECTCRE.match(line)
                if mo:
                    sectname = mo.group('header')
                    # This is where we have found an [Image] section
                    # and now need to create our object to stuff data into.
                    if sectname == "Image":
                        self.image_unique_id += 1
                        section = JigdoImage( self.log,
                                              self.async,
                                              self.settings,
                                              self,
                                              unique_id = self.image_unique_id )
                        self.images[self.image_unique_id] = section
                    # Here we have found the [Parts] section and need to create
                    # the object to stuff data into.
                    elif sectname == "Parts":
                        section = JigdoPartsDefinition(sectname, self.log)
                        self.parts = section
                    # Here we have found the [Servers] section and need to create
                    # the definition object to be able to add the options.
                    elif sectname == "Servers":
                        section = JigdoServersDefinition(sectname, self.log)
                        self.servers = section
                    # Here we have found our (pyjigdo's) new [Mirrorlists] section.
                    # This allows users to define a source to 'ping' for the most
                    # recent url lists for a give part. The part file name is appended to the
                    # request and we expect a list of valid (or thought to be valid) URLs
                    # for which we can iterate to find a server with the given file.
                    elif sectname == "Mirrorlists":
                        section = JigdoMirrorlistsDefinition(sectname, self.log)
                        self.mirrors = section
                    else:
                        section = JigdoDefinitionSection(sectname)
                    cursect = section
                    self._sections.append(section)
                    # So sections can't start with a continuation line
                    optname = None
                # no section header in the file?
                elif cursect is None:
                    raise MissingSectionHeaderError(fpname, lineno, line)
                # an option line?
                else:
                    mo = RawConfigParser.OPTCRE.match(line)
                    if mo:
                        optname, vi, optval = mo.group('option', 'vi', 'value')
                        if vi in ('=', ':') and ';' in optval:
                            # ';' is a comment delimiter only if it follows
                            # a spacing character
                            pos = optval.find(';')
                            if pos != -1 and optval[pos-1].isspace():
                                optval = optval[:pos]
                        optval = optval.strip()
                        # allow empty values
                        if optval == '""':
                            optval = ''
                        if not (isinstance(cursect, JigdoPartsDefinition) or \
                                isinstance(cursect, JigdoServersDefinition) or \
                                isinstance(cursect, JigdoMirrorlistsDefinition)):
                            optname = optname.rstrip().lower().replace("-","_")
                        cursect.add_option(optname,optval)
                    else:
                        # a non-fatal parsing error occurred.  set up the
                        # exception but keep going. the exception will be
                        # raised at the end of the file and will contain a
                        # list of all bogus lines
                        if not e:
                            e = ParsingError(fpname)
                        e.append(lineno, repr(line))
        # if any parsing errors occurred, raise an exception
        if e:
            raise e

    def create_objects(self):
        """ All data has been parsed into storage, create any remaining needed objects. """
        # This will create the JigdoRepoDefinitions
        if self.servers:
            self.servers.create_objects()
        else:
            self.log.error(_("[Servers] section is not present or can't be parsed. Abort!"), recoverable = False)
        # This will stuff the mirror information into the correct JigdoRepoDefinition
        if self.mirrors: self.mirrors.create_objects(self.servers)

class JigdoDefinitionSection:
    """ A Section in the Jigdo Definition File """
    def __init__(self, name, image_unique_id = 0):
        self._section_name = name

    def add_option(self,name, val = None):
        setattr(self,name,val)

class JigdoServersDefinition:
    """ The [servers] section of a jigdo configuration file. """
    def __init__(self, name, log):
        self._section_name = name
        self.log = log
        self.i = {}
        self.objects = {}

    def __str__(self):
        """ Return the contents of the definition.
            Note this is tab indented and return cleared. """
        server_data = []
        for (server_id, server_url_list) in self.i.iteritems():
            server_data.append("ID: %s\n\tURL(s): %s\n" % (server_id, " ".join(server_url_list)))
        return "\n".join(server_data)

    def add_option(self, name, val = None):
        try:
            if self.i[name]: pass
        except KeyError:
            self.i[name] = []
        self.i[name].append(val)

    def create_objects(self):
        """ Create the JigdoRepoDefinition objects based on what information we have
            in self.i (index). """
        for (server_id, server_url_list) in self.i.iteritems():
            self.objects[server_id] = JigdoRepoDefinition(server_id, server_url_list, self.log)

class JigdoMirrorlistsDefinition:
    """ The [mirrorlists] section of a jigdo configuration file.
        This is just a storage location for the data for which create_objects()
        is called upon to inject the mirrorlists into the JigdoRepoDefinition.
        To be able to use the [mirrorlists] definition, the backwards-compatable
        [servers] section must also be used with the same repo id. """
    def __init__(self, name, log):
        self._section_name = name
        self.log = log
        self.i = {}

    def __str__(self):
        """ Return the mirror lists we know about.
            Note this is tab indented and return cleared. """
        mirror_data = []
        for (mirror_id, mirror_list_urls) in self.i.iteritems():
            mirror_data.append("ID: %s\n\tURL(s): %s\n" % (mirror_id, " ".join(mirror_list_urls)))
        return "\n".join(mirror_data)

    def add_option(self, name, val = None):
        try:
            if self.i[name]: pass
        except KeyError:
            self.i[name] = []
        self.i[name].append(val)

    def create_objects(self, servers):
        """ Find the JigdoRepoDefinition and inject the mirrorlists into it. """
        for (repo_id, repo) in servers.objects.iteritems():
            try:
                #repo.mirrorlist = pyJigdo.misc.get_mirror_list(self.i[repo_id], self.log)
                self.log.debug(repo)
            except KeyError:
                self.log.warning(_("Server ID '%s' does not have a matching matching mirrorlist.") % repo_id)


class JigdoPartsDefinition:
    """ The [parts] section of a jigdo configuration file. """
    def __init__(self, name, log):
        self._section_name = name
        self.log = log
        self.i = {}

    def __getitem__(self, item):
        # Return the part data
        return self.i[item]

    def __str__(self):
        return "\tThere are %s files defined." % len(self.i)

    def add_option(self, name, val = None):
        self.i[name] = val

class JigdoRepoDefinition:
    """ A repo definition that can return an url for a given label.
        Baseurls and mirrorlist need to be lists. """
    def __init__(self, label, baseurls, log, mirrorlist=[], data_source=None):
        self.label = label
        self.baseurls = baseurls
        self.log = log
        self.mirrorlist = mirrorlist
        self.data_source = data_source

    def __str__(self):
        """ Return data about this JigdoRepo. """
        return "Label: '%s' \n\tBaseurls: %s \n\tMirrorlist: %s" % ( self.label,
                                                            self.baseurls,
                                                            self.mirrorlist )

    def get_url(self, file, priority=0, use_only_servers = False):
        """ Get a resolved url from this repo, given a file name and resolution priority.
            The higher the priority, the more direct a response will be given.
            If use_only_servers is True, only baseurls will be tried. """

        num_sources = len(self.baseurls) + len(self.mirrorlist)
        base_url = None
        if not priority and not use_only_servers:
            # Mirror lists: order of response from mirror list server, these are tried first
            # Servers: first listed -> down; meaning, try the first listed match
            # This can all be affected by using priority. The larger the priority, the more specific we
            # need for a response.
            if self.mirrorlist:
                base_url = self.mirrorlist[0]
            else:
                base_url = self.baseurls[0]
        elif use_only_servers:
            # Only look for a source defined by a [servers] section
            while not base_url and (priority > -1) and (priority < len(self.baseurls)):
                try:
                    base_url = self.baseurls[priority]
                except IndexError:
                    pass
                priority -= 1
        else:
            # Find the closest match to the priority requested.
            while not base_url and (priority > -1) and (priority < num_sources):
                try:
                    base_url = self.mirrorlist[priority]
                except IndexError:
                    try:
                        base_url = self.baseurls[priority]
                    except IndexError:
                        pass
                priority -= 1

        if not base_url: return None
        urldata = urlparse.urlsplit(base_url)
        url = urlparse.urljoin(base_url, file)
        try:
            if urldata.query:
                query = urldata.query
                while query.endswith('/'): query = query.rstrip('/')
                url = "%s://%s%s?%s/%s" % (urldata.scheme, urldata.netloc, urldata.path, query, file)
        except AttributeError:
            pass
        return url

class JigdoImage:
    """ An Image in the Jigdo Definition File, defining JigdoTemplate and JigdoImageSlices. """
    def __init__(self, log, async, settings, jigdo_definition, unique_id = 0):
        """ Setup JigdoImage() with needed relations. """
        self.log = log
        self.async = async
        self.settings = settings
        self.jigdo_definition = jigdo_definition
        self.selected = False
        self.finished = False
        self.unique_id = unique_id
        self.slices = {}
        self.download_tries = 0
        # These are filled in when parsing the .jigdo definition
        self.filename = ''
        self.filename_md5sum = ''
        self.template = ''
        self.template_md5sum = ''
        self.fs_location = ''
        self.target_location = self.settings.download_target
        self.location = ''
        self.tmp_location = ''

    def __str__(self):
        """ Return formatted information about the given image.
            Note this is tab indented and return cleared. """
        return "\tFilename: %s\n\tTemplate: %s\n\tTemplate MD5SUM: %s\n" % \
               (self.filename, self.template, self.template_md5sum)

    def source(self):
        """ Return the source location for this Jigdo template. """
        return self.template

    def target(self):
        """ Return the target location for this Jigdo template. """
        return self.fs_location

    def download_callback_success(self, ign):
        """ Callback entry point for when self.get() is successful. """
        self.download_tries += 1
        self.log.info(_("Successfully downloaded %s" % self.template))
        self.collect_slices()
        self.get_slices()
        self.log.debug(_("Ending download event for %s" % self.filename))

    def download_callback_failure(self, ign):
        """ Callback entry point for when self.get() fails. """
        self.download_tries += 1
        self.log.warning(_("Failed to download %s: \n\t%s" % ( self.filename,
                                                             ign )))
        if self.download_tries >= self.settings.max_download_attempts:
            self.log.error(_("Max tries for %s reached. Not downloading." % self.filename))
        else:
            self.async.request_download(self)
        self.log.debug(_("Failed download of %s, added new task to try again." % self.filename))

    def queue_download(self):
        """ Queue the self.get() in the async.
            First check to see if the template is already there and is complete. """
        if not self.fs_location:
            self.fs_location = url_to_file_name(self.template, self.target_location)
        if check_complete(self.log, self.fs_location, self.template_md5sum):
            self.download_callback_success(None)
        else:
            self.async.request_download(self)

    def get(self):
        """ Download the Jigdo template using the async.
            Return the async task. """
        if self.download_tries >= self.settings.max_download_attempts:
            attempt = "last"
        else:
            attempt = self.download_tries + 1
        self.log.status(_("Adding a task to download: %s (attempt: %s)" % \
                       (self.filename, attempt)))
        return self.async.download_object(self)

    def get_slices(self):
        """ Download the template file's defined slices. """
        # These calls start their own event driven calls and
        # we now leave the template object callback from the
        # JigdoTemplate download request.
        for jigdo_slice_hash,jigdo_slice in self.missing_slices().iteritems():
            jigdo_slice.queue_download()

    def add_option(self,name, val = None):
        setattr(self,name,val)

    def collect_slices(self):
        """ Collects the slices needed for this template. """
        self.location = os.path.join(self.target_location, self.filename)
        self.tmp_location = "%s.tmp" % self.location
        template_target = self.fs_location
        iso_exists = False
        if os.access(self.tmp_location, os.W_OK):
            template_target = self.tmp_location
            self.log.info(_("Temporary template found at %s" % template_target))
            # FIXME: Need a test to see if this tmp image is usable.
        template_data = self.async.jigdo_file.get_template_data(template_target)
        if os.access(self.location, os.R_OK): iso_exists = True
        for line in template_data:
            if line.startswith('need-file'):
                slice_hash = line.split()[3]
                (slice_server_id, slice_file_name) = self.jigdo_definition.parts[slice_hash].split(':')
                if not iso_exists: self.slices[slice_hash] = JigdoImageSlice( self.log, self.async,
                                                             self.settings,
                                                             slice_hash,
                                                             slice_file_name,
                                                             self.jigdo_definition.servers.objects[slice_server_id],
                                                             self.settings.download_storage )
            elif line.startswith('image-info'):
                self.filename_md5sum = line.split()[2]
                if iso_exists:
                    self.log.info(_("%s exists, checking..." % self.filename))
                    # FIXME: Duplicate check_file!! (See misc.py:120 and pyjigdo.py:416)
                    #if pyJigdo.misc.check_file(self.location, checksum = self.filename_md5sum):
                    #    self.log.info(_("%s is complete." % self.filename))
                    #    self.finished = True
                    #    self.selected = False
                    #    self.cleanup_template()

    def finished_slices(self):
        """ Returns a dictionary of slices that have been downloaded and marked as finished.
            This also checks if the slice has been added to the target image during this session. """
        finished_slices = {}
        for (slice_hash, slice_object) in self.slices.iteritems():
            if slice_object.finished and not slice_object.in_image:
                finished_slices[slice_hash] = slice_object
        return finished_slices

    def missing_slices(self):
        """ Returns a dictionary of slices that are not marked as finished. """
        missing_slices = {}
        for (slice_hash, slice_object) in self.slices.iteritems():
            if not slice_object.finished:
                missing_slices[slice_hash] = slice_object
        return missing_slices

    def select(self):
        self.selected = True

    def unselect(self):
        self.selected = False

    # FIXME: Duplicate check_file function!! (See misc.py:120)
    def check_self(self):
        """ Run checks on self to see if we are sane. """
        self.log.info(_("Checking image %s ..." % self.filename))
        #if pyJigdo.misc.check_file(self.location, checksum = self.filename_md5sum):
        #    self.log.info(_("%s is complete." % self.filename))
        #    self.finished = True
        #    self.cleanup_template()

    def cleanup_template(self):
        """ Remove un-needed data. """
        try:
            if os.access(self.tmp_location, os.R_OK):
                os.unlink(self.tmp_location)
        except OSError:
            pass

class JigdoImageSlice:
    """ A file needing to be downloaded for an image. """
    def __init__(self, log, async, settings, md5_sum, filename, repo, target_location):
        """ Initialize the ImageSlice """
        self.log = log
        self.async = async
        self.settings = settings
        self.slice_sum = md5_sum
        self.filename = filename
        self.repo = repo
        self.target_location = target_location
        self.fs_location = os.path.join( self.target_location,
                                         self.filename )
        self.current_source = None
        self.download_tries = 0
        self.finished = False
        self.in_image = False

    def __str__(self):
        """ Return information about this slice. """
        return "Filename: %s Repo: %s Target Location: %s" % ( self.filename,
                                                               self.repo.label,
                                                               self.fs_location )

    def source(self):
        """ Return the source location for this Jigdo slice. """
        self.new_source()
        return self.current_source

    def target(self):
        """ Return the target location for this Jigdo slice. """
        return self.fs_location

    def download_callback_success(self, ign):
        """ Callback entry point for when self.get() is successful. """
        self.download_tries += 1
        self.log.info(_("Successfully downloaded %s" % self.filename))
        self.log.debug(_("Ending download event for %s" % self.filename))

    def download_callback_failure(self, ign):
        """ Callback entry point for when self.get() fails. """
        self.download_tries += 1
        self.log.warning(_("Failed to download %s: \n\t%s" % ( self.filename,
                                                             ign )))
        if self.download_tries >= self.settings.max_download_attempts:
            self.log.error(_("Max tries for %s reached. Not downloading." % self.filename))
        else:
            #self.new_source()
            self.async.request_download(self)
        self.log.debug(_("Failed download of %s, added new task to try again." % self.filename))

    def queue_download(self):
        """ Queue the self.get() in the async.
            First check to see if the file is already there and is complete. """
        if check_complete(self.log, self.fs_location, self.slice_sum):
            self.download_callback_success(None)
        else:
            self.async.request_download(self)

    def get(self):
        """ Download the Jigdo slice using the async.
            Return the async task. """
        if self.download_tries >= self.settings.max_download_attempts:
            attempt = "last"
        else:
            attempt = self.download_tries + 1
        self.log.status(_("Adding a task to download: %s (attempt: %s)" % \
                       (self.filename, attempt)))
        return self.async.download_object(self)
 
    def new_source(self):
        """ Populate self.current_source with something we have not tried. """
        url = None
        servers_only = self.settings.servers_only
        if (self.download_tries >= self.settings.fallback_number): servers_only = True
        url = self.repo.get_url( self.filename,
                                 self.download_tries,

                                 use_only_servers = servers_only)
        if not url:
           self.download_tries = self.settings.max_download_attempts
        else:
           self.current_source = url

    def run_download(self, timeout, max_mirror_tries, total = None, pending = None):
        """ Download and confirm this slice.
            If the target_location exists, check to make sure it's the data we want."""
        if self.finished: return True
        title = self.file_name
        if total and pending: title = "[%s/%s] %s" % (total-pending+1, total, self.file_name)
        self.check_self(announce = True, title = title)
        attempt = 0
        servers_only = False
        while not self.finished:
            url = None
            if (attempt >= max_mirror_tries) and not servers_only:
                servers_only = True
                attempt = 0
            if servers_only:
                url = self.repo.get_url(self.file_name, attempt, use_only_servers = True)
            else:
                url = self.repo.get_url(self.file_name, attempt)
            if not url: return self.finished
            url_data = urlparse.urlparse(url)
            base_name = os.path.basename(self.file_name)
            self.log.info(_("Trying to download %s" % url))
            self.log.status(_("Trying %s for %s" % (url_data.netloc,
                                                    base_name)
                                                    ))
            #pyJigdo.misc.get_file(url,
            #                      file_target = self.file_name,
            #                      working_directory = self.target_location,
            #                      title = title,
            #                      timeout = timeout)
            self.check_self()
            attempt += 1
        return self.finished

    def check_self(self, announce = False, title = None):
        """ Run checks on self to see if we are sane. """
        local_file = self.location
        if not self.location:
            local_file = os.path.join(self.target_location, self.file_name)
        if not title: title = local_file
        #if pyJigdo.misc.check_file(local_file, checksum = self.slice_sum):
        #    if announce: self.log.info(_("%s exists and checksum matches." % title))
        #    self.location = local_file
        #    self.finished = True

class JigdoScanTarget:
    """ A definition of where to look for existing bits. """
    def __init__(self, location, cfg, log, needed_files, is_iso=False):
        self.location = location
        self.mounted = False
        self.mount_location = ""
        self.cfg = cfg
        self.log = log
        self.is_iso = is_iso
        self.needed_files = needed_files
        # Make location absolute:
        self.location = os.path.abspath(self.location)

    def run_scan(self):
        """ Scan a given location for needed file names and update the slice
            object with the found location for later use. """
        if self.is_iso: self.mount()
        self.log.info(_("Scanning %s for needed files..." % self.location))
        for (path, directories, files) in os.walk(self.location):
            for name in files:
                try:
                    self.log.status(_("Looking for file %s ..." % name))
                    target_slice = self.needed_files[name]
                    found_target = os.path.join(path, name)
                    target_slice.location = found_target
                    self.log.debug(_("Found file %s, marking location." % name))
                except KeyError:
                    # We don't need this file
                    pass

    def mount(self):
        """ Mount the ISO. """
        if self.mounted: return
        self.mount_location = os.path.join(self.cfg.working_directory,
                                           "mounts",
                                           os.path.basename(self.location))
        #pyJigdo.misc.check_directory(self.mount_location)
        mount_command = ["fuseiso",
                         "-p",
                         self.location,
                         self.mount_location]
        self.log.debug(_("Mounting %s at %s ..." % (self.location, self.mount_location)))
        #pyJigdo.misc.run_command(mount_command)
        self.mounted = True
        self.location = self.mount_location

    def unmount(self):
        """ Un-Mount the ISO. """
        if not self.mounted: return
        umount_command = ["fusermount", "-u", self.mount_location]
        #pyJigdo.misc.run_command(umount_command)

class JigdoJobPool:
    """ A pool to contain all our pending jobs.
        Use add_job to queue objects into specific run stack. """
    def __init__(self, log, cfg, jigdo_definition):
        self.log = log
        self.cfg = cfg
        self.jigdo_definition = jigdo_definition
        self.threads = 1 # Not really threaded, yet. This is still up for debate.
        self.max_threads = 10 # FIXME: Is actually a configuration option (10 makes a good default to play with though)
        self.checkpoint_frequency = 50 * self.threads
        self.current_checkpoint = self.checkpoint_frequency
        self.jobs = {
                        'scan': [],
                        'download': [],
                        'download_failures': [],
                        'compose': [],
                    }
        self.pending_jobs = 0
        self.total_jobs = 0

    def add_job(self, job_type, object):
        queue = self.jobs[job_type]
        self.log.debug(_("Adding a job for %s: %s" % (job_type, object)))
        queue.append(object)
        self.pending_jobs += 1
        self.total_jobs += 1
        if type(object) == "str":
            sys.exit(1)

    def checkpoint(self):
        """ Check if we need to do checkpointing tasks. """
        self.current_checkpoint -= 1
        if self.current_checkpoint <= 0:
            self.current_checkpoint = self.checkpoint_frequency
            # FIXME: Add checkpoint hooks/define what we do
            # during a checkpoint.
            # Stuff bits into target images:
            for (image_id, image) in self.jigdo_definition.images.iteritems():
                if not image.finished \
                and image.selected \
                and image.finished_slices(): self.add_job('compose', image)
            self.order_mirrors()

    def order_mirrors(self):
        """ Order the known sources based on average bitrates. """
        # FIXME: Implement the average bitrate stuff.
        # For now, it just randomizes the mirrors.
        # FIXME: Implement shuffling the servers, preserving the last listed
        # source as the fallback
        from random import shuffle
        if self.jigdo_definition.servers.objects:
            for (repo_id, repo) in self.jigdo_definition.servers.objects.iteritems():
                if repo.mirrorlist: shuffle(repo.mirrorlist)

    def do_scan(self, number=1, final_run=False):
        """ Scan a location for needed files and stuff them into our image.
            Order of logic is, match file name, match sum then stuff bits. """
        while number > 0 and self.jobs['scan']:
            task = self.jobs['scan'].pop(0)
            task.run_scan()
        if not final_run: self.checkpoint()

    def do_download(self, number=1, final_run=False):
        """ This is a hack around implementing the threading.
            For threaded, we will need to define something thread safe
            such as the JigdoDownloadJob class. """
        while number > 0 and self.jobs['download']:
            task = self.jobs['download'].pop(0)
            if not task.run_download(self.cfg.urlgrab_timeout,
                                     self.cfg.fallback_number,
                                     total = self.total_jobs,
                                     pending = self.pending_jobs):
                self.log.error(_("Download failed: %s" % task))
                self.add_job('download_failures', task)
            number -= 1
            self.pending_jobs -= 1
        if not final_run: self.checkpoint()

    def do_download_failures(self, requeue=True, report=False, number=1, final_run=False):
        """ Requeue what files failed to download that had been added to the queue.
            Optionally, report on the status. """
        if report and (len(self.jobs['download_failures']) > 0):
            self.log.info(_("The following downloads failed:"))
        for task in self.jobs['download_failures']:
            if report: self.log.info(_("Download of %s failed." % task))
            if requeue:
                self.log.debug(_("Re-queuing %s ..." % task.file_name))
                self.add_job('download', task)
            self.pending_jobs -= 1
        if requeue and not final_run: self.jobs['download_failures'] = []
        if not final_run: self.checkpoint()

    def do_compose(self, number=1, final_run=False):
        """ Take what bits we know about and stuff them into the Jigdo image.
            This will run given number of pending compose jobs. """
        while number > 0 and self.jobs['compose']:
            task = self.jobs['compose'].pop(0)
            if not task.finished:
                self.log.info(_("Stuffing bits into Jigdo image %s...") % task.filename)
                for (slice_hash, slice) in task.finished_slices().iteritems():
                    self.stuff_bits_into_image(task, slice.location)
                    # FIXME: Check if we succeeded or not:
                    slice.in_image = True
            number -= 1
            self.pending_jobs -= 1
        if not final_run: self.checkpoint()

    def do_final_compose(self):
        """ Run a compose against all enabled images, just to make sure we didn't miss
            anything. """
        for (image_id, image) in self.jigdo_definition.images.iteritems():
            if not image.finished \
            and image.selected \
            and image.finished_slices():
                self.add_job('compose', image)
        added_jobs = len(self.jobs['compose'])
        if added_jobs: self.do_compose(added_jobs,
                                       final_run=True)

    def stuff_bits_into_image(self, jigdo_image, file, destroy=False):
        """ Put given file into given jigdo_image.
            If destroy, the bits will be removed after being added to the
            target image. """
        self.log.debug(_("Stuffing %s into %s ..." % (file,
                                                      os.path.basename(jigdo_image.location))))
        command = [ "jigdo-file", "make-image",
                    "--image", jigdo_image.location,
                    "--template", jigdo_image.fs_location,
                    "--jigdo", self.jigdo_definition.file_name,
                    "-r", "quiet",
                    "--force",
                    file ]
        #pyJigdo.misc.run_command(command, inshell=True)
        if destroy: os.remove(file)

    def do_last_queue(self):
        """ Try one last time to queue up the needed actions. """
        for (image_id, image) in self.jigdo_definition.images.iteritems():
            if not image.finished and image.selected:
                # FIXME: We might not want to do this, but other things should
                # be done in do_last_queue, so please don't remove
                for (slice_hash, slice) in image.missing_slices().iteritems():
                    self.add_job('download', slice)

    def finish_pending_jobs(self):
        """ Check all queues and run remaining tasks. """
        self.do_last_queue()
        self.current_checkpoint = 0
        self.checkpoint()
        for (type, queue) in self.jobs.iteritems():
            action = getattr(self, 'do_%s' % type)
            self.log.debug(_("Running %s for:\n %s" % (
                            "do_%s" % type,
                            queue)))
            if len(queue): action(number=len(queue), final_run=True)
        self.do_final_compose()
        for leftovers in self.jobs.itervalues():
            if leftovers: return False
        return True


