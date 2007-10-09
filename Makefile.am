# Automake Automagic

EXTRA_DIST =               \
    intltool-extract.in    \
    intltool-merge.in      \
    intltool-update.in     \
    pyjigdo.spec.in        \
    pyjigdo.spec           \
    ChangeLog              \
    COPYING                \
    AUTHORS                \
    README                 \
    pyjigdo.py

DISTCLEANFILES =           \
    intltool-extract       \
    intltool-merge         \
    intltool-update

SUBDIRS =                  \
    conf                   \
    pyjigdo                \
    po

execdir = $(sbindir)
install-exec-local:
	mkdir -p $(DESTDIR)$(bindir)
	$(INSTALL) -m 755 pyjigdo.py $(DESTDIR)$(bindir)/pyjigdo

uninstall-local:
	rm -f $(DESTDIR)$(pkgdatadir)/pixmaps/*.png
	rm -f $(DESTDIR)$(pkgdatadir)/ui/*
	rm -f $(DESTDIR)$(bindir)/pyjigdo

clean:
	rm -f *.pyo *.pyc *.py~
	find -type f -name "*.pyo" -exec rm -f {} \;
	find -type f -name "*.pyc" -exec rm -f {} \;
	find -type f -name "*.py~" -exec rm -f {} \;
	find -type f -name "*.gladep" -exec rm -rf {} \;
	find -type f -name "*.glade.bak" -exec rm -rf {} \;
	rm -f *~
	rm -f pyjigdo.spec
	rm -f config.status config.log
	rm -rf autom4te.cache/
	find -type f -name "Makefile" -exec rm -f {} \;
	find -type f -name "Makefile.in" -exec rm -f {} \;
	find -type f -name "*.log" -exec rm -f {} \;
	find -type f -name "pyjigdo-*.tar.gz" -exec mv -f {} .. \;
	rm -f aclocal.m4 configure intltool-extract intltool-merge intltool-update po/POTFILES


rpm: dist
	@(rpmbuild -ta pyjigdo-$(PACKAGE_VERSION).tar.gz)

srpm: dist
	@(rpmbuild -ts pyjigdo-$(PACKAGE_VERSION).tar.gz)

CVS_PKGVERSION=`echo $(PACKAGE_VERSION) | sed -e 's/\./_/g'`
CVSTAG=$(PACKAGE_NAME)-$(CVS_PACKAGEVERSION)
tag:
	@cvs tag -F $(CVSTAG)
