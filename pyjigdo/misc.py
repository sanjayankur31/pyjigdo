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

import base64
import os
import re
import shutil
import subprocess
import sys
import types
import time
import urlgrabber
import urlgrabber.grabber
import urlgrabber.progress
import urlparse

import pyjigdo
import pyjigdo.progress

import pyjigdo.translate as translate
from pyjigdo.translate import _, N_

try:
    # new versions of python. Use hashlib
    import hashlib as md5_hashlib
except ImportError:
    # old versions of python. Use now deprecrated md5
    import md5 as md5_hashlib

def jigdo_info(url):
    """Prints out information about a .jigdo file located at the given URL"""

    # This should use a function to grab the file with, parse it, display the info and destroy all the temp data
    try:
        urlgrabber.urlgrab(url, "/var/tmp/jigdo.jigdo", copy_local=1)
    except Exception, e:
        print >> sys.stderr, "%r" % e.__class__
        print >> sys.stderr, "Exception raised"

    for section in jigdo_config.getSections():
        print '** %s:' % section[0]
        misc.printOut(section[1], 0)
        #print section[1]
    sys.exit(1)

def get_file(url, working_directory = "/var/tmp"):
    """Gets a file from url and returns the file name (full path)"""
    file_basename = os.path.basename(urlparse.urlparse(url).path)
    file_name = os.path.join(working_directory, file_basename)

    if not check_file(file_name, destroy = True):
        # File does not exist or wasn't valid. Download the file.
        download_file(url, file_name)
    else:
        # There should be no else to this one
        pass

    return file_name

def download_file(url, file_name, title=None):
    pbar = pyjigdo.progress.ProgressCLI("Downloading")
    dlcb = pyjigdo.progress.dlcb(pbar)
    urlgrabber.urlgrab(url, file_name, copy_local=1, progress_obj=dlcb)

def check_file(file_name, checksum = None, destroy = False):
    """
    Checks if a file exists. Basically returns True if the file exists, unless the
    checksum doesn't check out or destroy has been set to True.

    If the file exists:
        Checksum:
            If specified, run the checksum and return:
                - True if the checksum checks out.
                - False if it doesn't and destroy the file.
            If not specified:
                - Continue
        Destroy:
            If True:
                - Destroy the file and return False
            else:
                - Return True
    else:
        - return False

    """
    if os.access(file_name, os.R_OK):
        if not checksum == None:
            if file_checksum(file_name, checksum):
                return True
            else:
                return False
        elif destroy:
            os.remove(file_name)
            return False
        else:
            return True
    else:
        return False

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

## We need to set a default path in env= so that if shell=False, we don't bail out
## os.getenv so that $PATH is respected...
# ^ Turns out this wasn't the problem, but it's nice to have.
temp_env = {'PATH': os.getenv('PATH')}
def run_command(command, rundir=None, inshell=False, env=temp_env, stdout=subprocess.PIPE, show=False):
    """ Run a command and return output. Remember command must be ['command', 'arg1', 'arg2'] """
    if rundir == None:
        rundir = options.download_workdir

    check_directory(rundir)
    if options.debug: print "Running command '%s'" % command

    ret = []
    p = subprocess.Popen(command, cwd=rundir, stdout=stdout, stderr=subprocess.STDOUT, shell=False, env=env)
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

def check_directory(directory, destroy=False):
    """ Check if directory exists. If not, create it or fail. """
    if not os.access(directory, os.R_OK):
        try:
            os.makedirs(directory)
        except OSError:
            print _("Directory %s could not be created. Aborting" % directory)
            sys.exit(1)
    #elif destroy:
        # Ask for confirmation?
        #shutil.rmtree(directory)
        #os.makedirs(directory)

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
        file_name = os.path.basename(urlparse.urlparse(options_instance.jigdo_source).path)
    except AttributeError:
        file_name = options.jigdo_source
    jigdo_local_file = os.path.join(options_instance.download_workdir, file_name)
    try:
        jigdo_source = urlgrabber.urlgrab(options_instance.jigdo_source, filename=jigdo_local_file,
        	progress_obj=TextMeter())
    except urlgrabber.urlgrabError:
        print _("Unable to fetch %s" % options_instance.jigdo_source)
        sys.exit(1)
    return file_name, jigdo_local_file, jigdo_source

