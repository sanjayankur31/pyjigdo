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
Parsing the configuration file(s)
"""
import os, os.path
import re, sys

from ConfigParser import ConfigParser
from urlgrabber import urlread
from urlgrabber.grabber import URLGrabError

import rhpl.translate as translate
from rhpl.translate import _, N_

class CustomParser(ConfigParser):
    """ Custom class to make sure we preserve case. """
    def optionxform(self, option):
        return str(option)

class jigdoDefinition:
    """ The Jigsaw definition file """
    def __init__(self, definition_file_loc, mirror_file_loc, download_workdir):
        """ Let's init the configuration.
            @param definition_file_loc: Definition file location
            @param mirror_file_loc: Mirror file location"""
        self.definition_file_loc = definition_file_loc
        self.parser = CustomParser()
        self.__allSections = []
        self.cache_dir = os.path.join(download_workdir, "cache")
        self.cache_db = os.path.join(self.cache_dir, "jigdo-cache.db")
        self.mirror_geo = {}
        self.mirror_global = {}
        self.mirror_fallback = {}
        self.mirror_preferred = {}
        self.mirror_num = 0
        self.jigdo_url = ""
        self.scan_dirs = []
        self.scan_isos = []
        print _("Reading jigdo configuration...")
        self.parse()
        
    def parse(self):
        """ Do the actual parsing """
        self.definition_file = open(self.definition_file_loc, 'r')
        self.parser.readfp(self.definition_file)
        # readfp seeks to end - Reset file
        self.definition_file.seek(0)
        toSearch = re.compile('(\n\[Image\].*\[)', re.DOTALL | re.I)
        content = self.definition_file.read()
        if not content:
            print _('You have supplied an empty file, valid jigsaw definition required.')
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
                # This will break if there are any query options
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
                if section in ("Servers"):
                    # We'll do this one later:
                    pass
                else:
                    # this makes a dict of {'Key', 'Value} from the parser
                    getattr(self, section)[option] = self.parser.get(section, option)
            self.__allSections.append([section, getattr(self, section)])
        self.definition_file.close()
        # Read all the contents of the jigdo definition and extract the full [Servers] seciton
        servers_search = re.compile('(\n\[Servers\].*?\[)', re.DOTALL | re.I)
        servers_section = re.search(servers_search, content)
        servers_section_str = servers_section.string[servers_section.span()[0]+1:servers_section.span()[1]-1]
        server_dict = {}
        for line in servers_section_str.split('\n'):
            if len(line.split('=')) > 1:
                key, value = line.split('=', 1)
                try:
                    server_dict[key].append(value)
                except KeyError:
                    server_dict[key] = [value]
            else:
                continue
        for item in server_dict.keys():
            self.Servers[item] = server_dict[item]
        return True
        
    def getSections(self):
        """ Return all sections used from the config """
        return self.__allSections
        
    def buildMirrors(self):
        """ Fetch full URLS from our mirror list and populate. """
        mirror_id = 1
        for server_id in self.Servers.keys():
            for server_url in self.Servers[server_id]:
                self.mirror_fallback[mirror_id] = [server_id, server_url]
                mirror_id += 1
        try:
            global_mirrorlist_urls = []
            for server_id in self.Mirrorlists.keys():
                try:
                    data = urlread(self.Mirrorlists[server_id]).splitlines()
                    global_mirrorlist_urls.append("%s&country=global" % self.Mirrorlists[server_id])
                    for data_item in data:
                        if not re.compile("#").search(data_item):
                            self.mirror_geo[mirror_id] = [server_id, data_item + "/"]
                            mirror_id += 1
                except URLGrabError:
                    print "Failed fetching mirror list from %s not adding mirrors from this source..." % self.Mirrorlists[server_id]
            for mirror_url in global_mirrorlist_urls:
                try:
                    global_data = urlread(mirror_url).splitlines()
                    for data_item in global_data:
                        if not (re.compile("#").search(data_item)) and not (data_item in self.mirror_geo.keys()):
                            self.mirror_global[mirror_id] = [server_id, data_item + "/"]
                            mirror_id += 1
                except URLGrabError:
                    print "Failed fetching mirror list from %s not adding mirrors from this source..." % mirror_url


        except AttributeError:
            print "No mirror lists defined, not building mirror lists."
        self.mirror_num = mirror_id - 1


