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

import logging, math, os, rpm, sys, time, urllib2
import urlgrabber, urlgrabber.progress

# Import constants
from pyjigdo.constants import *

import pyjigdo.translate as translate
from pyjigdo.translate import _, N_

##
##
## CLI Progress Bars
##
##

class ProgressCLI:
    def __init__(self, title = ""):
        """All we want is a widget. It's new, so it's set to fraction 0.0"""
        self.title = title
        self.txt = ''
        self.fract = 0.0
        self.columns = os.getenv("$COLUMNS", 80)
        self.space_left = 0
        self.space_right = 3
        self.reserved_left = 31
        self.reserved_right = 6
        self.set_fraction(self.fract)
        #if len(self.title) > 29:
            #print self.title
            #self.title = ' ' * 29

    def show(self):
        pass

    def destroy(self):
        self.set_fraction(1.0)
        sys.stdout.write('\r\n')
        sys.stdout.flush()

    def set_fraction(self, fract):
        if fract <= 1.0:
            self.fract = fract

            room = self.columns - self.space_left - self.space_right - self.reserved_left - self.reserved_right

            perc = math.floor(fract*100)
            show = int(room*perc/100)
            not_show = room - show
            sys.stdout.write('\r' + self.title + ': ' + str(' ' * (self.columns - len(self.title))) + ' ')
            sys.stdout.write('\r' + self.title + ': ' + str(' ' * (self.reserved_left - len(self.title))) + str('#' * show) + str(' ' * not_show) + str(' ' * (self.reserved_right-len(str(perc)))) + str(perc) + '% ' + str(self.txt))
            sys.stdout.flush()

    def get_fraction(self):
        return self.fract

    def set_markup(self, txt):
        self.txt = txt

    def set_pbar_text(self, txt):
        pass

class dlcb(urlgrabber.progress.BaseMeter):
    def __init__(self, pbar, log = None, cfg = None):
        urlgrabber.progress.BaseMeter.__init__(self)
        self.log = log
        self.cfg = cfg
        self.pbar = pbar
        self.last = time.time()

    def _do_start(self, now):
        self.pbar.set_fraction(0.0)

    def _do_end(self, amount_read, now=None):
        self.pbar.set_fraction(amount_read / self.size)

    def _do_update(self, amount_read, now=None):
        if self.size is None:
            return
        pct = float(amount_read) / float(self.size)
        self.re.update(amount_read, now)
        self.pbar.set_markup(self.re.remaining_time() + ' ETA')
        self.pbar.set_fraction(pct)
        self.last = time.time()

class dlcb(urlgrabber.progress.TextMeter):
    def __init__(self, pbar, log = None, cfg = None):
        urlgrabber.progress.BaseMeter.__init__(self)
        self.log = log
        self.cfg = cfg
        self.pbar = pbar
        self.last = time.time()

    def _do_start(self, now):
        self.pbar.set_fraction(0.0)

    def _do_end(self, amount_read, now=None):
        self.pbar.set_fraction(amount_read / self.size)

    def _do_update(self, amount_read, now=None):
        if self.size is None:
            return
        pct = float(amount_read) / float(self.size)
        self.re.update(amount_read, now)
        self.pbar.set_markup(self.re.remaining_time() + ' ETA')
        self.pbar.set_fraction(pct)
        self.last = time.time()
