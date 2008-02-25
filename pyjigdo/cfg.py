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

from ConfigParser import SafeConfigParser
import os

import pyjigdo.translate as translate
from pyjigdo.translate import _, N_

class ConfigStore:
    def __init__(self, base):
        self.base = base
        self.log = base.log
        self.cli_options = base.cli_options
        self.parser = base.parser
        self.defaults = Defaults()

        # This is where we check our parser for the defaults being set there.
        self.set_defaults_from_cli_options()

        # But, they should be available in our class as well
        for option in self.defaults.__dict__.keys():
            setattr(self,option,self.defaults.__dict__[option])

    def set_defaults_from_cli_options(self):
        for long_opt in self.parser.__dict__['_long_opt'].keys():
            if long_opt == "--help":
                continue
            setattr(self.defaults,self.parser._long_opt[long_opt].dest,self.parser._long_opt[long_opt].default)

    def setup_cfg(self):
        """This sets up the configuration store. An existing self.log is mandatory"""
        # First set the options from the configuration file
        self.options_set_from_config()

        # Then override those with the command line specified options
        self.options_set_from_commandline()

        # Now that we know about any of the options, it's about time we check them!
        self.check_options()

    def check_options(self):
        """Check the CLI options specified"""

        if self.cli_options.jigdo_url == "" and self.cli_mode:
            self.log.error(_("Running from CLI but no .jigdo file specified"), recoverable = False)

        if ( self.cli_options.jigdo_info and self.cli_options.jigdo_url == self.defaults.jigdo_url ):
            self.log.error(_("Info requested from a .jigdo file but no .jigdo file specified"), recoverable = False)

    def options_set_from_config(self):
        """Sets the default configuration options for pyjigdo from a
        configuration file. Configuration file may be customized using
        the --config CLI option"""

        self.log.debug(_("Setting options from configuration file"), level = 4)

        # Check from which configuration file we should get the defaults
        # Other then default?
        if not self.cli_options.config == self.defaults.config:
            self.config = self.cli_options.config

        config = self.check_config()
        self.load_config(config)

    def check_config(self, val=None):
        """Checks self.config or the filename passed using 'val' and returns a SafeConfigParser instance"""

        if val:
            config_file = val
        else:
            config_file = self.config

        if not os.access(config_file, os.R_OK):
            self.log.debug(_("Configuration file %s not readable, continuing without") % config_file, level = 1)
            return None

        config = SafeConfigParser()
        self.log.debug(_("Reading configuration file %s") % config_file, level = 9)
        try:
            config.read(config_file)
        except:
            self.log.warning(_("Invalid configuration file %s") % config_file)

        #if not config.has_section("pyjigdo"):
            #self.log.warning(_("No master configuration section [pyjigdo] in configuration file %s") % config_file)

        return config

    def load_config(self, config):
        """Given a SafeConfigParser instance, loads a PyJigdo Configuration file and checks,
        then sets everything it can find."""
        if config == None: return

        if config.has_section("pyjigdo"):
            # Walk this section and see if for each item, there is also
            # a default. Because, if there is no default, it cannot be set
            for varname in self.defaults.__dict__.keys():
                if not config.has_option("pyjigdo",varname):
                    continue

                if isinstance(self.defaults.__dict__[varname], int):
                    val = config.getint("pyjigdo",varname)
                elif isinstance(self.defaults.__dict__[varname], bool):
                    val = config.getboolean("pyjigdo",varname)
                elif isinstance(self.defaults.__dict__[varname], str):
                    val = config.get("pyjigdo",varname)
                elif isinstance(self.defaults.__dict__[varname], list):
                    val = eval(config.get("pyjigdo",varname))
                elif isinstance(self.defaults.__dict__[varname], dict):
                    val = eval(config.get("pyjigdo",varname))

                if hasattr(self,"check_setting_%s" % varname):
                    exec("retval = self.check_setting_%s(%r)" % (varname, val))
                    if not retval:
                        # We just don't set it, check_setting_%s should have
                        # taken care of the error messages
                        continue

                if not self.defaults.__dict__[varname] == val:
                    setattr(self,varname,val)
                    self.log.debug(_("Setting %s to %r (from configuration file)") % (varname,val))

    def options_set_from_commandline(self):
        """Overrides default options from the CLI"""
        self.log.debug(_("Setting options from command-line"))

        config = SafeConfigParser()
        config.read(self.config)

        # Now set the rest of the CLI options to
        for option in self.cli_options.__dict__.keys():
            if not self.cli_options.__dict__[option] == self.defaults.__dict__[option]:
                if hasattr(self,"check_setting_%s" % option):
                    exec("retval = self.check_setting_%s(%r)" % (option, self.cli_options.__dict__[option]))
                    if not retval:
                        continue
                    else:
                        setattr(self,option,self.cli_options.__dict__[option])
                        self.log.debug(_("Setting %s to %r (from command line)") % (option,self.cli_options.__dict__[option]), level = 8)
                else:
                    self.log.debug(_("No check_setting_%s()") % option, level = 9)
                    setattr(self,option,self.cli_options.__dict__[option])
                    self.log.debug(_("Setting %s to %r (from command line)") % (option,self.cli_options.__dict__[option]), level = 8)
            else:
                self.log.debug(_("Setting %s to %r (from command line)") % (option,self.cli_options.__dict__[option]), level = 8)

    def _set_gui_mode(self):
        self.gui_mode = True
        self.cli_mode = False

    def _set_cli_mode(self):
        self.gui_mode = False
        self.cli_mode = True

class Defaults:
    def __init__(self):
        pass
