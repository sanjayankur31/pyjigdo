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

import os, os.path
import sys
import subprocess
import base64
import types
import time
import re

from urlgrabber import urlgrab
from urlparse import urlparse
from urlgrabber.grabber import URLGrabError
from urlgrabber.progress import TextMeter

import rhpl.translate as translate
from rhpl.translate import _, N_

from interfaces import options

try:
    # new versions of python. Use hashlib	
    import hashlib as md5_hashlib
except ImportError:
    # old versions of python. Use now deprecrated md5
    import md5 as md5_hashlib


class LoopbackMount:
    def __init__(self, lofile, mountdir, fstype = None):
        self.lofile = lofile
        self.mountdir = mountdir
        self.fstype = fstype

        self.mounted = False
        self.losetup = False
        self.rmdir   = False
        self.loopdev = None

    def __getitem__(self, key):
        """ Make object['item'] --> object.item """
        return getattr(self, key)

    def __setitem__(self, key, value):
        """ Make object['item'] --> object.item """
        return setattr(self, key, value)

    def cleanup(self):
        self.umount()
        self.lounsetup()

    def umount(self):
        if self.mounted:
            rc = subprocess.call(["/bin/umount", self.mountdir])
            self.mounted = False

        if self.rmdir:
            try:
                os.rmdir(self.mountdir)
            except OSError, e:
                pass
            self.rmdir = False

    def lounsetup(self):
        if self.losetup:
            rc = subprocess.call(["/sbin/losetup", "-d", self.loopdev])
            self.losetup = False
            self.loopdev = None

    def loopsetup(self):
        if self.losetup:
            return

        rc = subprocess.call(["/sbin/losetup", "-f", self.lofile])
        if rc != 0:
            raise MountError(_("Failed to allocate loop device for '%s'") % self.lofile)

        # succeeded; figure out which loopdevice we're using
        buf = subprocess.Popen(["/sbin/losetup", "-a"],
                               stdout=subprocess.PIPE).communicate()[0]
        for line in buf.split("\n"):
            # loopdev: fdinfo (filename)
            fields = line.split()
            if len(fields) != 3:
                continue
            if fields[2] == "(%s)" % (self.lofile,):
                self.loopdev = fields[0][:-1]
                break

        if not self.loopdev:
            raise MountError(_("Failed to find loop device associated with '%s' from '/sbin/losetup -a'") % self.lofile)

        self.losetup = True

    def mount(self):
        if self.mounted:
            return

        self.loopsetup()

        if not os.path.isdir(self.mountdir):
            os.makedirs(self.mountdir)
            self.rmdir = True

        args = [ "/bin/mount", self.loopdev, self.mountdir ]
        if self.fstype:
            args.extend(["-t", self.fstype])

        rc = subprocess.call(args)
        if rc != 0:
            raise MountError(_("Failed to mount '%s' to '%s'") % (self.loopdev, self.mountdir))

        self.mounted = True

class MountError(Exception):
    def __init__(self, msg):
        Exception.__init__(self, msg)

def run_command(command, rundir=None, inshell=False, env=None, stdout=subprocess.PIPE, show=False):
    """ Run a command and return output. """
    if rundir == None:
        rundir = options.download_workdir

    check_directory(rundir)
    if options.debug: print "Running command '%s'" % command

    ret = []
    p = subprocess.Popen(command, cwd=rundir, stdout=stdout, stderr=subprocess.STDOUT, shell=False)
    while p.poll() == None:
        for item in p.stdout.read().split('\n'):
            ret.append(item)
        time.sleep(0.01)
    for item in p.stdout.read().split('\n'):
        ret.append(item)
    p.stdout.close()
    #if options.debug:
    #    print "\n==== %s Output ====\n%s\n==== End Output ====\n" % (' '.join(command), '\n'.join(ret))
    return ret

#    p = subprocess.Popen(command, cwd=rundir, stdout=stdout, stderr=subprocess.STDOUT, shell=inshell, bufsize=1)
#'''    ret = []
#    while True:
#    	s = select.select([p.stdout], [], [], 0.001)
#    	if len(s[0]) > 0:
#    		line = p.stdout.readline()
#    		if show:
#    			sys.stdout.write(line)
#    		ret.append(line)
#	if p.poll() != None:
#    		break'''
#    ret = p.communicate()[0].split('\n')
#    p.stdout.close()
#    return ret

def check_directory(directory):
    """ Check if directory exists. If not, create it or fail. """
    if not os.access(directory, os.R_OK):
        try:
            os.makedirs(directory)
        except OSError:
            print _("Directory %s could not be created. Aborting" % directory)
            sys.exit(1)

def compare_sum(target, base64_sum):
    """ Compares a file's sum to given sum. """
    B, K, M, G = 1, 1024, 1024*1024, 1024*1024*1024
    # now that our sizes are defined let's do some multiplication
    bufsize = 8*K*B
    mode = 'rb'
    if not os.path.isfile(target): return False
    f = open(target, mode)
    md5 = md5_hashlib.md5()
    try:
        while True: # this just reads to the end and updates the hash
            temp_data = f.read(bufsize)
            if not temp_data:
                f.close()
                break
            md5.update(temp_data)
    except Exception, error_description:
        # eventually let's actually do something here when it fails
        print 'An error occurred while running checksum: %s' % error_description
        return False
    calc = md5.digest()
    base64_calc = base64.urlsafe_b64encode(calc)
    eq = re.compile('=')
    base64_strip = eq.sub('', base64_calc)
    if options.debug:
        print _("Checking %s against %s..." % (base64_strip, base64_sum))
    if base64_strip == base64_sum:
        return True
    else:
        return False

def sortDictValues(adict):
    keys = adict.keys()
    keys.sort()
    return map(adict.get, keys)

def printOut(dictionary, loop):
    """ Print out a dict """
    addStr = '\t'
    endStr = '--> '
    fullLoopStr = addStr
    for number in range(loop):
        fullLoopStr += addStr
    fullLoopStr += endStr
    for key, value in dictionary.iteritems():
        if type(key) == types.DictType: # loop
            printOut(key, loop+1)
        elif type(value) == types.DictType:
            print '%s%s:' % (fullLoopStr, key)
            printOut(value, loop+1)
        else:
            print '%s%s:\t%s' % (fullLoopStr, key, value)

def getFileName(options_instance):
    """ Returns the propery filename. options is interfaces.options """
    try:
        file_name = os.path.basename(urlparse(options_instance.jigdo_source).path)
    except AttributeError:
        file_name = options.jigdo_source
    jigdo_local_file = os.path.join(options_instance.download_workdir, file_name)
    try:
        jigdo_source = urlgrab(options_instance.jigdo_source, filename=jigdo_local_file,
        	progress_obj=TextMeter())
    except URLGrabError:
        print _("Unable to fetch %s" % options_instance.jigdo_source)
        sys.exit(1)
    return file_name, jigdo_local_file, jigdo_source

