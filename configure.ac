AC_INIT([pyjigdo], 0.2)
AC_CONFIG_SRCDIR(pyjigdo/__init__.py.in)

#ALL_LINGUAS="bn_IN bn ca cs da de el es fi fr gl gu hi hr hu is it ja ko ml ms nb nl or pa pl pt pt_BR ru sk sl sr@Latn sr sv ta tr uk zh_CN zh_TW"

AM_INIT_AUTOMAKE
AM_MAINTAINER_MODE
AM_PATH_PYTHON

dnl prevent to copy po/Makefile.in.in
GETTEXT_PACKAGE=pyjigdo
AC_SUBST(GETTEXT_PACKAGE)
AM_GLIB_GNU_GETTEXT
AC_PROG_INTLTOOL
AC_PROG_LN_S

AM_PATH_PYTHON

AC_CONFIG_FILES([
conf/Makefile
doc/Makefile
po/Makefile.in
Makefile
pyjigdo.spec
pyjigdo/Makefile
pyjigdo/__init__.py
])

AC_OUTPUT
