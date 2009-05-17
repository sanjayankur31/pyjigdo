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
from random import shuffle
from ConfigParser import RawConfigParser

from pyJigdo.userinterface import SelectImages
from pyJigdo.util import url_to_file_name, check_complete, run_command, check_directory

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
            if self.select_images(): self.get_templates()
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
        return self.image_selection.run()

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
                        section = JigdoMirrorlistsDefinition( sectname,
                                                              self.log,
                                                              self.async,
                                                              self.settings )
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
            self.log.critical(_("[Servers] section is not present or can't be parsed. Abort!"))
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
    def __init__(self, name, log, async, settings):
        self._section_name = name
        self.log = log
        self.async = async
        self.settings = settings
        self.i = {}
        self.servers = None
        self.mirror_data = {} # {repo_id: {download_tries: n, data: [] },}

    def fetch_callback_success(self, ign, repo_id=None):
        """ Callback entry point for when self.get() is successful. """
        for l in ign.split('\n'):
            if not l.startswith("#"): self.mirror_data[repo_id]["data"].append(l.rstrip('\n'))
        self.log.info(_("Successfully downloaded %s" % repo_id))
        self.mirror_data[repo_id]["download_tries"] += 1
        self.add_results(repo_id)
        self.log.debug(_("Ending download event for mirrorlist %s" % repo_id))

    def fetch_callback_failure(self, ign, repo_id=None):
        """ Callback entry point for when self.get() fails. """
        self.mirror_data[repo_id]["download_tries"] += 1
        self.log.warning(_("Failed to download mirrorlist %s: \n\t%s" % ( repo_id,
                                                               ign )))
        if self.mirror_data[repo_id]["download_tries"] >= self.settings.max_download_attempts:
            self.log.error(_("Max tries for mirrorlist %s reached. Not downloading." % repo_id))
        else:
            self.async.request_fetch(self)
        self.log.debug(_("Failed download of mirrorlist %s, added new task to try again." % repo_id))

    def get(self, repo_id):
        """ Download the Mirror lists file using the async.
            Return the async task. """
        if self.mirror_data[repo_id]["download_tries"] >= self.settings.max_download_attempts:
            attempt = "last"
        else:
            attempt = self.mirror_data[repo_id]["download_tries"] + 1
        self.log.status(_("Adding a task to download mirrorlist for: %s (attempt: %s)" % \
                       (repo_id, attempt)))
        # FIXME: Support multiple mirror list sources.
        return self.async.fetch_data( self.i[repo_id][0],
                                      self.fetch_callback_success,
                                      self.fetch_callback_failure,
                                      repo_id )

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

    def add_results(self, repo_id):
        """ Take the mirror list results and add them to the correct servers section. """
        try:
            shuffle(self.mirror_data[repo_id]["data"])
            self.servers.objects[repo_id].mirrorlist = self.mirror_data[repo_id]["data"]
        except KeyError, e:
            self.log.error(_("Failed to add mirror list for repo %s: %s" % (repo_id, e)))

    def create_objects(self, servers):
        """ Find the JigdoRepoDefinition, add a task to download the mirror list
            data. Gracefully fail if there is not a match. """
        self.servers = servers
        for (repo_id, repo) in self.servers.objects.iteritems():
            try:
                check_mirrorlist = self.i[repo_id]
                self.mirror_data[repo_id] = { "download_tries": 0,
                                              "data": [] }
                self.get(repo_id)
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
    def __init__(self, label, baseurls, log, mirrorlist=[]):
        self.label = label
        self.baseurls = baseurls
        self.log = log
        self.mirrorlist = mirrorlist
        self.history = {} # { file: [base_url,] }

    def __str__(self):
        """ Return data about this JigdoRepo. """
        return "Label: '%s' \n\tBaseurls: %s \n\tMirrorlist: %s" % \
               ( self.label, self.baseurls, self.mirrorlist )

    def get_url(self, file, use_only_servers = False):
        """ Get a resolved url from this repo, given a file name.
            If use_only_servers is True, only baseurls will be tried. """
        base_url = None
        # Make sure we have a history for this file.
        try:
            c = self.history[file]
        except KeyError:
            self.history[file] = []
        
        if use_only_servers:
            # Only look for a source defined by a [servers] section
            # Always try all [servers]
            for source in self.baseurls:
                if source not in self.history[file]:
                    base_url = source
                    self.history[file].append(source)
                    break
        else:
            # Find a mirror we have not tried yet.
            source_list = self.mirrorlist + self.baseurls
            if not (len(self.history[file]) >= len(source_list)):
                for source in source_list:
                    if source not in self.history[file]:
                        base_url = source
                        self.history[file].append(source)
                        break

        self.log.debug(_("Sourced base URL %s for file %s" % (base_url, file)))
        self.log.debug(_("File %s history: %s" % (file, " ".join(self.history[file]))))

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
        self.scan_targets = [] # [ JigdoScanTarget(), ]
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
        self.scan_local_sources()
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
                                                             self.settings.download_storage,
                                                             self )
            elif line.startswith('image-info'):
                self.filename_md5sum = line.split()[2]
                if iso_exists:
                    self.log.info(_("%s exists, checking..." % self.filename))
                    if check_complete( self.log, self.location, self.filename_md5sum):
                        self.log.status(_("%s is complete and located at %s" % \
                                         ( self.filename, self.location) ))
                        self.finished = True
                        self.selected = False
                        self.cleanup_template()

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

    def cleanup_template(self):
        """ Remove un-needed data. """
        try:
            if os.access(self.tmp_location, os.R_OK):
                os.unlink(self.tmp_location)
        except OSError:
            pass

    def scan_local_sources(self):
        """ Check to see if we have been given any local sources
            to scan for data before downloading. """
        slices_by_filename = {}
        for (k, s) in self.slices.items():
            slices_by_filename[ s.filename ] = s
        for scan_dir in self.settings.scan_dirs:
            d = JigdoScanTarget( self.log,
                                 self.settings,
                                 scan_dir,
                                 slices_by_filename )
            self.scan_targets.append( d )
        for scan_iso in self.settings.scan_isos:
            i = JigdoScanTarget( self.log,
                                 self.settings,
                                 scan_iso,
                                 slices_by_filename,
                                 is_iso = True )
            self.scan_targets.append( i )
        for scan_target in self.scan_targets:
            scan_target.run_scan()

    def notify_slice_done(self):
        """ The main checkpoint callback to stuff data into the ISO. """
        ready_slices = self.finished_slices()
        if len(ready_slices.keys()) >= self.settings.download_stuff_bits:
            self.stuff_data()

    def stuff_data(self):
        """ Stuff data into the target ISO file. """
        for slice in self.finished_slices().values():
            if self.async.jigdo_file.stuff_bits_into_image( self,
                                                            slice.fs_location,
                                                            destroy = self.settings.download_stuff_then_remove ):
                slice.in_image = True

    def finish(self):
        """ Finish processing this template.
            Complain if we are not really done. """
        self.log.debug(_("finish() has been called on %s, stuffing data." % self.filename))
        self.stuff_data()
        if self.missing_slices():
            # FIXME: Do something other then complain.
            self.log.critical(_("finish() was called on template %s, but there is missing data!" % self.filename))
            return False
        self.log.status(_("ISO Image %s is complete and located at %s" % ( self.filename,
                                                                           self.location )))
        return True

class JigdoImageSlice:
    """ A file needing to be downloaded for an image. """
    def __init__(self, log, async, settings, md5_sum, filename, repo, target_location, template):
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
        self.template = template
        self.current_source = None
        self.download_tries = 0
        self.finished = False
        self.in_image = False

    def __str__(self):
        """ Return information about this slice.
            Note this is tab indented and return cleared. """
        return "\tFilename: %s\n\tRepo: %s\n\tTarget Location: %s\n" % \
               ( self.filename, self.repo.label, self.fs_location )

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
        # FIXME: Verify we have gotten the data we want.
        self.finished = True
        self.template.notify_slice_done()
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
            First check to see if the file is already there and is complete. """
        if check_complete(self.log, self.fs_location, self.slice_sum):
            self.log.status(_("Requested data %s was found and is complete." % self.filename))
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
                                 use_only_servers = servers_only)
        if not url:
           self.download_tries = self.settings.max_download_attempts
        else:
           self.current_source = url

class JigdoScanTarget:
    """ A definition of where to look for existing bits. """
    def __init__(self, log, settings, location, needed_files, is_iso=False):
        self.log = log
        self.settings = settings
        self.location = location
        self.mounted = False
        self.mount_location = ""
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
                    # Wow, this is a hack. There has got to be a better way to do this.
                    # This will likely break... a lot.
                    target_name = os.path.join(path, name).split(self.location)[1].strip('/')
                    # / hack, or is it? ;-)
                    target_slice = self.needed_files[target_name]
                    self.log.debug(_("Found file %s checking match..." % name))
                    found_target = os.path.join(path, name)
                    if check_complete(self.log, found_target, target_slice.slice_sum):
                        self.log.info(_("Found a matching file during scan: %s" % name))
                        target_slice.fs_location = found_target
                        target_slice.finished = True
                    else:
                        self.log.info(_("Found a matching file, but it did not sum: %s" % name))
                except KeyError:
                    # We don't need this file, hopefully
                    self.log.debug(_("Ignoring non-matching file %s" % name))

    def mount(self):
        """ Mount the ISO. """
        if self.mounted: return
        self.mount_location = os.path.join(self.settings.download_storage,
                                           "mounts",
                                           os.path.basename(self.location))
        check_directory(self.log, self.mount_location)
        mount_command = ["fuseiso",
                         "-p",
                         self.location,
                         self.mount_location]
        self.log.debug(_("Mounting %s at %s ..." % (self.location, self.mount_location)))
        run_command( self.log, self.settings, mount_command )
        self.mounted = True
        self.location = self.mount_location

    def unmount(self):
        """ Un-Mount the ISO. """
        if not self.mounted: return
        umount_command = ["fusermount", "-u", self.mount_location]
        run_command( self.log, self.settings, umount_command )

