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

import os

from urlparse import urlparse

import pyJigdo.translate as translate
from pyJigdo.translate import _, N_

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

