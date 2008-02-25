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
from ConfigParser import RawConfigParser
import pyjigdo
import urlparse

from urlgrabber import urlgrab
from urlgrabber.grabber import URLGrabError
from urlgrabber.progress import TextMeter
from urlgrabber import urlread

import pyjigdo.translate as translate
from pyjigdo.translate import _, N_

class JigdoDefinition:
    """A Jigdo Definition File"""
    def __init__(self, file_name):
        self.file_name = file_name
        self.image_unique_id = 0
        self.images = { }
        self.parse()

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
            if line.strip() == '' or line[0] in '#;':
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
                    if sectname == "Image":
                        self.image_unique_id += 1
                        section = JigdoImage(self.image_unique_id)
                        self.images[self.image_unique_id] = section
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

class JigdoDefinitionSection:
    """A Section in the Jigdo Definition File"""
    def __init__(self, name, image_unique_id = 0):
        self._section_name = name

    def add_option(self,name, val = None):
        setattr(self,name,val)

class JigdoImage:
    """An Image in the Jigdo Definition File. Collection of JigdoImageSlices"""
    def __init__(self, unique_id = 0):
        self.selected = False
        self.unique_id = unique_id
        self.slices = { }

    def add_option(self,name, val = None):
        setattr(self,name,val)

    def collect_slices(self):
        """Collects the slices needed for this template"""
        print self.__dict__
        template_data = pyjigdo.misc.run_command(["jigdo-file", "ls", "--template", self.template_name], inshell=True)

    def select(self):
        self.selected = True

    def unselect(self):
        self.selected = False

class JigdoImageSlice:
    """A file needing to be downloaded for an image."""
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

class JigdoJob:
    def __init__(self):
        pass

class JigdoDownloadJob(JigdoJob):
    def __init__(self):
        pass

class JigdoJobPool:
    def __init__(self):
        self.threads = 0
        self.max_threads = 10 # FIXME: Is actually a configuration option (10 makes a good default to play with though)
        self.jobs = {
                        'scan': {},
                        'download': {},
                        'loopmount': {},
                        'compose': {},
                    }

    def add_job(self, job_type = None, object = None):
        pass