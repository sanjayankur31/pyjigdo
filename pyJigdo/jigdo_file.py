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
jigdo-file calls and functions. These need to be implemented directly, without
shelling out for this information. For now, we just shell out to jigdo-file.
"""

import subprocess, os, time
from pyJigdo.util import check_directory

import pyJigdo.translate as translate
from pyJigdo.translate import _, N_


class execJigdoFile:
    """ A class to shell out to jigdo-file and return
        data from commands. """
    def __init__(self, log, settings, jigdo_file):
        """ Use given jigdo-file to perform operations. """
        self.log = log
        self.settings = settings
        self.jigdo_file = jigdo_file
        self.jigdo_env = {'PATH': os.getenv('PATH')}

    def get_template_data(self, template_file):
        """ Return the template data from the given template_file. """
        # TODO: Return an object, not just the output.
        return self.run_command(["jigdo-file", "ls", "--template", template_file], inshell=True)


    def run_command(self, command, rundir=None, inshell=False, env=None, stdout=subprocess.PIPE):
        """ Run a command and return output. Remember command must be ['command', 'arg1', 'arg2'] """
        ret = []
        if not rundir: rundir = self.settings.download_storage
        check_directory(self.log, rundir)
        if not env: env = self.jigdo_env
        if not command: return ""
        self.log.debug(_("Running command: '%s'" % " ".join(command)))
        p = subprocess.Popen(command, cwd=rundir, stdout=stdout, stderr=subprocess.STDOUT, shell=False, env=env)
        while p.poll() == None:
            for item in p.stdout.read().split('\n'):
                ret.append(item)
            time.sleep(0.01)
        for item in p.stdout.read().split('\n'):
            ret.append(item)
        p.stdout.close()
        return ret
