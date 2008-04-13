#
# Copyright 2007 Fedora Unity
#
# Jonathan Steffan <jon a fedoraunity.org>
# Jeroen van Meeuwen <kanarip a fedoraunity.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; version 2 only
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.

import logging
import logging.handlers
import sys

import pyjigdo.translate as translate
from pyjigdo.translate import _, N_

class Logger:
    def __init__(self, loglevel = logging.INFO, debuglevel = 0):
        self.loglevel = loglevel
        self.debuglevel = debuglevel

        plaintextformatter = logging.Formatter("%(message)s")

        console_stdout = logging.StreamHandler(sys.stdout)
        console_stdout.setFormatter(plaintextformatter)

        filelog_handler = logging.FileHandler(filename = "pyjigdo.log")
        filelog_handler.setFormatter(plaintextformatter)

        self.log = logging.getLogger()
        self.log.addHandler(console_stdout)
        self.log.addHandler(filelog_handler)

        self.log.setLevel(self.loglevel)

    def set_config(self, cfg):
        """Let the Logger instance know what our configuration is and she might
        be able to distinct between CLI and GUI mode, or even give more details
        about what goes wrong"""
        self.cfg = cfg
    
    def status(self, msg):
        """ Send a status. If len() > 79, data will be truncated. """
        if len(msg) > 79: msg = "%s..." % msg[:76]
        print '%s%s\r' % (msg, " "*(79 - len(str(msg)))),
        sys.stdout.flush()

    def info(self, msg):
        self.log.info(msg)

    def debug(self, msg, level = 1):
        # By default, level = 1 so that debug messages are suppressed
        if level <= self.debuglevel:
            self.log.debug(msg)

    def error(self, msg, recoverable = True):
        self.log.error(msg)
# FIXME: Add OK/Cancel box for recoverable in GUI mode
        if self.cfg.gui_mode:
            self.error_box(msg)
        elif self.cfg.cli_mode:
            if recoverable:
                self.error_prompt(msg)
            else:
                sys.exit(1)

    def warning(self, msg):
        self.log.warning(msg)
        if self.cfg.gui_mode:
# FIXME: Add OK/Cancel box for recoverable in GUI mode
            self.warning_box(msg)
        elif self.cfg.cli_mode:
            self.warning_prompt(msg)

    def error_box(self, text):
        """Display an Error Message Box"""
        import gtk
        dlg = gtk.MessageDialog(None, 0, gtk.MESSAGE_ERROR, gtk.BUTTONS_OK, text)
        dlg.set_title(_("Error"))
        dlg.set_default_size(100, 100)
        dlg.set_position (gtk.WIN_POS_CENTER)
        dlg.set_border_width(2)
        dlg.set_modal(True)
        dlg.run()
        dlg.hide()
        dlg.destroy()
        self._runGtkMain()

    def warning_box(self, text):
        """Display an Error Message Box"""
        if not self.cfg.answer_yes:
            import gtk
            dlg = gtk.MessageDialog(None, 0, gtk.MESSAGE_WARNING, gtk.BUTTONS_OK, text)
            dlg.set_title(_("Warning"))
            dlg.set_default_size(100, 100)
            dlg.set_position (gtk.WIN_POS_CENTER)
            dlg.set_border_width(2)
            dlg.set_modal(True)
            dlg.run()
            dlg.hide()
            dlg.destroy()
            self._runGtkMain()

    def error_prompt(self, text):
        """The error has already been logged to the console, try and catch some input"""
        if self.cfg.cli_mode and not self.cfg.answer_yes:
            sys.stderr.write(_("Do you want to continue? [Y/n]") + " ")
            answer = sys.stdin.readline()[:-1]
            if answer == "n":
                self.error(_("Abort! Abort! Abort!"), recoverable = False)
                sys.exit(1)

    def warning_prompt(self, text):
        """The error has already been logged to the console, try and catch some input"""
        if self.cfg.cli_mode and not self.cfg.answer_yes:
            sys.stdout.write(_("Do you want to continue? [Y/n]") + " ")
            answer = sys.stdin.readline()[:-1]
            if answer == "n":
                self.error(_("Abort! Abort! Abort!"), recoverable = False)
                sys.exit(1)

    # Master GTK Interface update routine
    def _runGtkMain(*args):
        import gtk
        while gtk.events_pending():
            gtk.main_iteration()
