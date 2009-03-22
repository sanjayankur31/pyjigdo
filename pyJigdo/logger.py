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

import logging, sys
from logging import DEBUG, INFO, WARNING, ERROR, CRITICAL

class pyJigdoLogger:
    def __init__(self, logfile, loglevel=WARNING, file_loglevel=INFO):
        """ pyJigdoLogger is used to log to the interface and to a file.
            Default is to prefer logging more data to a file and less to
            to console. """

        self.loglevel = loglevel
        self.file_loglevel = file_loglevel

        console_logging = logging.Formatter("%(message)s")
        file_logging = logging.Formatter("%(asctime)s - %(message)s")

        console_stdout = logging.StreamHandler(sys.stdout)
        console_stdout.setFormatter(console_logging)
        console_stdout.setLevel(self.loglevel)

        filelog_handler = logging.FileHandler(filename = logfile)
        filelog_handler.setFormatter(file_logging)
        filelog_handler.setLevel(self.file_loglevel)

        self.log = logging.getLogger()
        self.log.setLevel(DEBUG)
        self.log.addHandler(console_stdout)
        self.log.addHandler(filelog_handler)

    def debug(self, msg):
        """ Log a debug level event. """
        self.log.debug(msg)

    def info(self, msg):
        """ Log an info level event. """
        self.log.info(msg)

    def warning(self, msg):
        """ Log a warning level event. """
        self.log.warning("Warning: %s" % msg)

    def error(self, msg):
        """ Log an error level event. """
        self.log.error("\nError: %s\n" % msg)

    def critical(self, msg):
        """ Log a critical level event. """
        self.log.critical("\nCRITICAL: %s\n" % msg)

