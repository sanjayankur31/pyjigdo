#!/bin/env bash
# Reconfigure automake scripts/files

function need_deps {
  echo "Some dependencies might be missing. Install them."
  echo "On Fedora: yum install automake autoconf gettext intltool glib glib2-devel"
  exit 1
}


if command -v autoreconf >/dev/null; then
  autoreconf -v
else
  echo "autoreconf/automake is missing. Install it..."
  need_deps
fi

if [ "$?" -ne "0" ]; then
  echo -e "\nWas not able to reconfigure!"
  echo -e "See above output for the reason.\n\n"
  need_deps
fi

./configure
