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
Utility functions, shared across classes.
"""

import os, re, base64

from urlparse import urlparse

try:
    # Py2.5
    import hashlib as md5_hashlib
except ImportError:
    # Py2.4
    import md5 as md5_hashlib

import pyJigdo.translate as translate
from pyJigdo.translate import _, N_

eq = re.compile('=')
B, K, M, G = 1, 1024, 1024*1024, 1024*1024*1024

def image_numstr_to_list(image_numstr):
    """ Expand a comma-separated list of image numbers and ranges into a list.
        e.g.: "1,2,  3, 5-8, 12" -> [1,2,3,5,6,7,8,12] """
    # First, eliminate all the commas
    image_numstr = image_numstr.replace(',', ' ')
    
    # Then, split and expand ranges, if any
    image_numstrs = image_numstr.split()
    expanded_image_numstrs = []
    for choice in image_numstrs:
        if '-' in choice:
            range_start, range_end = choice.split('-')
            try:
                range_start = int(range_start)
                range_end = int(range_end)
                if range_start <= range_end:
                    step = 1
                else:
                    step = -1
                expanded_image_numstrs.extend(range(range_start, range_end + step, step))
            except ValueError, e:
                self.log.error(_("Invalid range selection."), recoverable = True)
                continue
        else:
            expanded_image_numstrs.append(choice)
    return expanded_image_numstrs

def url_to_file_name(url, target_directory):
    """ Take an URL and a directory we want to put the file in
        and return an absolute path to the target filename. """
    file_basename = os.path.basename(urlparse(url).path)
    file_name = os.path.join(target_directory, file_basename)
    return file_name

def check_directory(log, directory):
    """ Check if directory exists. If not, try to create it. """
    if not os.access(directory, os.R_OK):
        log.debug(_("Going to try to create %s..." % directory))
        try:
            os.makedirs(directory)
        except OSError, e:
            log.critical(_("Directory %s could not be created!" % directory))
    elif not os.path.isdir(directory):
        log.critical(_("%s exists, but is not a directory!" % directory))

def check_complete(log, file, hash):
    """ Check to see if file is on disk and matches hash. """
    if os.access(file, os.R_OK) and check_hash(log, file, hash):
        log.debug(_("File %s is already downloaded and is complete." % file))
        return True
    elif os.path.isfile(file):
        log.debug(_("File %s is not complete. Marking for re-download." % file))
    return False

def check_hash(log, file, hash):
    """ Hash a file and see if it matches given hash. """
    matches = False
    if os.path.isfile(file):
        bufsize = 8*K*B
        mode = 'rb'
        try:
            f = open(file, mode)
            md5 = md5_hashlib.md5()
            while True:
                d = f.read(bufsize)
                if not d:
                    f.close()
                    break
                md5.update(d)
            md5_digest = md5.digest()
            base64_md5_digest = base64.urlsafe_b64encode(md5_digest)
            file_hash = eq.sub('', base64_md5_digest)
            log.debug(_("Checking %s against %s for %s ..." % \
                       (file_hash, hash, file)))
            if file_hash == hash: matches = True
        except Exception, e:
            log.warning(_("Reading file %s failed: %s" % (file, e)))
    return matches
