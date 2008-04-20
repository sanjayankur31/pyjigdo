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
"""
Implementation of Jigdo concepts, calling jigdo-file when needed.
"""

import os, urlparse, sys
import pyjigdo.misc
from ConfigParser import RawConfigParser

import pyjigdo.translate as translate
from pyjigdo.translate import _, N_

class JigdoDefinition:
    """ A Jigdo Definition File.
        just_print is used to suppress the creation of objects. """
    def __init__(self, file_name, log, cfg, just_print = False):
        self.file_name = file_name
        self.log = log
        self.cfg = cfg
        self.image_unique_id = 0
        self.images = {}
        self.parts = None
        self.servers = None
        self.mirrors = None
        self.parse()
        if not just_print: self.create_objects()

    def list_images(self):
        """ Print the details about all images. """
        self.log.info(_("==== Images defined in Jigdo ===="))
        for (image_id, image) in self.images.iteritems():
            self.log.info(_("Image Number %s:\n\t %s" % (image_id, image)))

    def print_information(self):
        """ Print the contents of the definition. """
        self.log.info(_("==== Servers listed in Jigdo ===="))
        self.log.info(self.servers)
        self.log.info(_("==== Mirror list sources listed in Jigdo ===="))
        self.log.info(self.mirrors)
        self.log.info(_("==== Images defined in Jigdo ===="))
        for (image_id, image) in self.images.iteritems():
            self.log.info(_("Number %s:\n\t %s" % (image_id, image)))
        self.log.info(_("==== Parts defined in Jigdo ===="))
        self.log.info(self.parts)


    def parse(self):
        """This parses the JigdoDefinition.file_name"""
        cursect = None                            # None, or a dictionary
        optname = None
        lineno = 0
        e = None                                  # None, or an exception
        self._sections = []

        fp = open(self.file_name, "r")
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
                        section = JigdoImage(self.log, self.cfg.destination_directory, unique_id = self.image_unique_id)
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
#                    print "Found section with name %s" % sectname
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
                        # XXX: So, isinstance() is useful here, but should we use it?!
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
        """ Print the contents of the definition. """
        server_data = []
        for (server_id, server_url_list) in self.i.iteritems():
            server_data.append("ID: %s URL(s): %s" % (server_id, " ".join(server_url_list)))
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
        """ Print the mirror lists we know about. """
        mirror_data = []
        for (mirror_id, mirror_list_urls) in self.i.iteritems():
            mirror_data.append("ID: %s URL(s): %s" % (mirror_id, " ".join(mirror_list_urls)))
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
                repo.mirrorlist = pyjigdo.misc.get_mirror_list(self.i[repo_id], self.log)
                self.log.debug(repo, level = 5)
            except KeyError:
                self.log.debug(_("Server ID '%s' does not have a matching matching mirrorlist.") % repo_id, level = 2)


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
        return "There are %s files defined." % len(self.i)

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
    def __init__(self, log, destination_dir, unique_id = 0):
        self.log = log
        self.selected = False
        self.finished = False
        self.unique_id = unique_id
        self.slices = {}
        # These are filled in when parsing the .jigdo definition
        self.filename = ''
        self.filename_md5sum = ''
        self.template = ''
        self.template_md5sum = ''
        self.template_file = ''
        self.target_location = destination_dir
        self.location = ''
        self.tmp_location = ''

    def __str__(self):
        """ Print information about the given image. """
        return "Filename: %s Template: %s Template MD5SUM: %s" % (self.filename,
                                                                   self.template,
                                                                   self.template_md5sum)

    def add_option(self,name, val = None):
        setattr(self,name,val)

    def collect_slices(self, jigdo_definition, work_dir):
        """ Collects the slices needed for this template. """
        self.location = os.path.join(self.target_location, self.filename)
        self.tmp_location = "%s.tmp" % self.location
        template_target = self.template_file
        iso_exists = False
        if os.access(self.tmp_location, os.W_OK):
            template_target = self.tmp_location
            self.log.debug(_("Temporary template found at %s" % template_target), level = 4)
            # FIXME: Need a test to see if this tmp image is usable.
        template_data = pyjigdo.misc.run_command(["jigdo-file", "ls", "--template", template_target], inshell=True)
        if os.access(self.location, os.R_OK): iso_exists = True
        for line in template_data:
            if line.startswith('need-file'):
                slice_hash = line.split()[3]
                (slice_server_id, slice_file_name) = jigdo_definition.parts[slice_hash].split(':')
                if not iso_exists: self.slices[slice_hash] = JigdoImageSlice(slice_hash,
                                                          slice_file_name,
                                                          jigdo_definition.servers.objects[slice_server_id],
                                                          work_dir,
                                                          self.log)
            elif line.startswith('image-info'):
                self.filename_md5sum = line.split()[2]
                if iso_exists:
                    self.log.info(_("%s exists, checking..." % self.filename))
                    # FIXME: Duplicate check_file!! (See misc.py:120 and pyjigdo.py:416)
                    if pyjigdo.misc.check_file(self.location, checksum = self.filename_md5sum):
                        self.log.info(_("%s is complete." % self.filename))
                        self.finished = True
                        self.selected = False
                        self.cleanup_template()

    def finished_slices(self):
        """ Returns a dictionary of slices that have been downloaded and marked as finished. """
        finished_slices = {}
        for (slice_hash, slice_object) in self.slices.iteritems():
            if slice_object.finished:
                finished_slices[slice_hash] = slice_object.location
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

    def get_template(self, work_dir):
        """ Make sure we have the template and it checks out, or fetch it again. """
        self.template_file = pyjigdo.misc.url_to_file_name(self.template, work_dir)
        if pyjigdo.misc.check_file(self.template_file, checksum = self.template_md5sum):
            self.log.info("Template %s exists and checksum matches." % self.template_file)
        else:
            self.template_file = pyjigdo.misc.get_file(self.template, working_directory = work_dir)
            if not pyjigdo.misc.check_file(self.template_file, checksum = self.template_md5sum):
                # FIXME: Prompt user asking if we should clear this data, try again?
                self.log.error("Template data for %s does not match defined checksum. Disabling image." % self.filename)
                self.unselect()

    # FIXME: Duplicate check_file function!! (See misc.py:120)
    def check_self(self):
        """ Run checks on self to see if we are sane. """
        if pyjigdo.misc.check_file(self.location, checksum = self.filename_md5sum):
            self.log.info(_("%s is complete." % self.filename))
            self.finished = True
            self.cleanup_template()

    def cleanup_template(self):
        os.unlink(self.tmp_location)

class JigdoImageSlice:
    """ A file needing to be downloaded for an image. """
    def __init__(self, md5_sum, file_name, repo, target_location, log):
        """ Initialize the ImageSlice """
        self.location = ""
        self.finished = False
        self.slice_sum = md5_sum
        self.file_name = file_name
        self.repo = repo
        self.target_location = target_location
        self.log = log

    def __str__(self):
        """ Return information about this slice. """
        return "Filename: %s Repo: %s Target Location: %s" % (self.file_name,
                                                               self.repo,
                                                               self.target_location)

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
            self.log.debug(_("Trying to download %s" % url), level = 4)
            self.log.status(_("Trying %s for %s" % (url_data.netloc,
                                                    base_name)
                                                    ))
            pyjigdo.misc.get_file(url,
                                  file_target = self.file_name,
                                  working_directory = self.target_location,
                                  title = title,
                                  timeout = timeout)
            self.check_self()
            attempt += 1
        return self.finished

    def check_self(self, announce = False, title = None):
        """ Run checks on self to see if we are sane. """
        local_file = self.location
        if not self.location:
            local_file = os.path.join(self.target_location, self.file_name)
        if not title: title = local_file
        if pyjigdo.misc.check_file(local_file, checksum = self.slice_sum):
            if announce: self.log.info(_("%s exists and checksum matches." % title))
            self.location = local_file
            self.finished = True

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
        self.log.debug(_("Scanning %s for needed files..." % self.location), level=3)
        for (path, directories, files) in os.walk(self.location):
            for name in files:
                try:
                    self.log.status(_("Looking for file %s ..." % name))
                    target_slice = self.needed_files[name]
                    found_target = os.path.join(path, name)
                    target_slice.location = found_target
                    self.log.debug(_("Found file %s, marking location." % name), level=3)
                except KeyError:
                    # We don't need this file
                    pass

    def mount(self):
        """ Mount the ISO. """
        if self.mounted: return
        self.mount_location = os.path.join(self.cfg.working_directory,
                                           "mounts",
                                           os.path.basename(self.location))
        pyjigdo.misc.check_directory(self.mount_location)
        mount_command = ["fuseiso",
                         "-p",
                         self.location,
                         self.mount_location]
        self.log.debug(_("Mounting %s at %s ..." % (self.location, self.mount_location)), level=3)
        pyjigdo.misc.run_command(mount_command)
        self.mounted = True
        self.location = self.mount_location

    def unmount(self):
        """ Un-Mount the ISO. """
        if not self.mounted: return
        umount_command = ["fusermount", "-u", self.mount_location]
        pyjigdo.misc.run_command(umount_command)

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
        queue.append(object)
        self.pending_jobs += 1
        self.total_jobs += 1

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

    def do_scan(self, number=1):
        """ Scan a location for needed files and stuff them into our image.
            Order of logic is, match file name, match sum then stuff bits. """
        while number > 0 and self.jobs['scan']:
            task = self.jobs['scan'].pop(0)
            task.run_scan()
        self.checkpoint()

    def do_download(self, number=1):
        """ This is a hack around implementing the threading.
            For threaded, we will need to define something thread safe
            such as the JigdoDownloadJob class. """
        while number > 0 and self.jobs['download']:
            task = self.jobs['download'].pop(0)
            if not task.run_download(self.cfg.urlgrab_timeout,
                                     self.cfg.fallback_number,
                                     total = self.total_jobs,
                                     pending = self.pending_jobs):
                self.jobs['download_failures'].append(task)
            number -= 1
            self.pending_jobs -= 1
        self.checkpoint()

    def do_download_failures(self, requeue=True, report=False, number=1):
        """ Requeue what files failed to download that had been added to the queue.
            Optionally, report on the status. """
        if report and (len(self.jobs['download_failures']) > 0):
            self.log.info(_("The following downloads failed:"))
        for task in self.jobs['download_failures']:
            if report: self.log(_("Download of %s failed." % task))
            if requeue: self.jobs['download'].append(task)
        if requeue: self.jobs['download_failures'] = []
        self.checkpoint()

    def do_compose(self, number=1):
        """ Take what bits we know about and stuff them into the Jigdo image.
            This will run given number of pending compose jobs. """
        while number > 0 and self.jobs['compose']:
            task = self.jobs['compose'].pop(0)
            if not task.finished:
                self.log.info(_("Stuffing bits into Jigdo image %s...") % task.filename)
                for (slice_hash, slice_location) in task.finished_slices().iteritems():
                    self.stuff_bits_into_image(task, slice_location)
            number -= 1
            self.pending_jobs -= 1
        self.checkpoint()

    def stuff_bits_into_image(self, jigdo_image, file, destroy=False):
        """ Put given file into given jigdo_image.
            If destroy, the bits will be removed after being added to the
            target image. """
        self.log.debug(_("Stuffing %s into %s ..." % (file, jigdo_image.location)), level=5)
        command = [ "jigdo-file", "make-image",
                    "--image", jigdo_image.location,
                    "--template", jigdo_image.template_file,
                    "--jigdo", self.jigdo_definition.file_name,
                    "-r", "quiet",
                    "--force",
                    file ]
        pyjigdo.misc.run_command(command, inshell=True)
        if destroy: os.remove(file)

    def do_last_queue(self):
        """ Try one last time to queue up the needed actions. """
        for (image_id, image) in self.jigdo_definition.images.iteritems():
            if not image.finished and image.selected:
                pending = image.missing_slices()
                for slice in pending:
                    self.add_job('download', slice)

    def finish_pending_jobs(self):
        """ Check all queues and run remaining tasks. """
        self.do_last_queue()
        self.current_checkpoint = 0
        self.checkpoint()
        for (type, queue) in self.jobs.iteritems():
            action = getattr(self, 'do_%s' % type)
            if len(queue): action(number=(len(queue)))
        for leftovers in self.jobs.itervalues():
            if leftovers: return False
        return True


