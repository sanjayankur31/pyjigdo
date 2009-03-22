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
    pyjigdo_interface.py

DISTCLEANFILES =           \
    intltool-extract       \
    intltool-merge         \
    intltool-update

SUBDIRS =                  \
    conf                   \
    doc                    \
    pyJigdo                \
    po

execdir = $(sbindir)
install-exec-local:
	mkdir -p $(DESTDIR)$(bindir)
	$(INSTALL) -m 755 pyjigdo_interface.py $(DESTDIR)$(bindir)/pyjigdo

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
	rm -f pyjigdo/__init__.py


rpm: dist
	@(rpmbuild -ta pyjigdo-$(PACKAGE_VERSION).tar.gz)

srpm: dist
	@(rpmbuild -ts pyjigdo-$(PACKAGE_VERSION).tar.gz)

CVS_PKGVERSION=`echo $(PACKAGE_VERSION) | sed -e 's/\./_/g'`
CVSTAG=$(PACKAGE_NAME)-$(CVS_PACKAGEVERSION)
tag:
	@cvs tag -F $(CVSTAG)

RELEASE=`rpm -q --qf="%{RELEASE}\n" --specfile $(PACKAGE).spec | head -n 1`

F-7: srpm
	@(mock -r fedora-7-i386 rebuild ~/rpmbuild/SRPMS/$(PACKAGE)-$(PACKAGE_VERSION)-$(RELEASE).src.rpm)

F-8: srpm
	@(mock -r fedora-8-i386 rebuild ~/rpmbuild/SRPMS/$(PACKAGE)-$(PACKAGE_VERSION)-$(RELEASE).src.rpm)

devel: srpm
	@(mock -r fedora-devel-i386 rebuild ~/rpmbuild/SRPMS/$(PACKAGE)-$(PACKAGE_VERSION)-$(RELEASE).src.rpm)

EL-5: srpm
	@(mock -r fedora-5-i386-epel rebuild ~/rpmbuild/SRPMS/$(PACKAGE)-$(PACKAGE_VERSION)-$(RELEASE).src.rpm)

mock: srpm F-7 F-8 devel EL-5

RELEASE_NUM=`rpm -q --qf="%{RELEASE}\n" --specfile $(PACKAGE).spec | head -n 1 | cut -d'.' -f 1`

fpeople: mock
	rm -rf public_html
	mkdir -p public_html/$(PACKAGE)/$(PACKAGE_VERSION)-$(RELEASE_NUM)/{el5,fc7,fc8,fc9}
	cp $(PACKAGE)-$(PACKAGE_VERSION).tar.gz public_html/$(PACKAGE)/$(PACKAGE_VERSION)-$(RELEASE_NUM)/.
	cp $(PACKAGE).spec public_html/$(PACKAGE)/$(PACKAGE_VERSION)-$(RELEASE_NUM)/.
	cp /var/lib/mock/epel-5-i386/result/* public_html/$(PACKAGE)/$(PACKAGE_VERSION)-$(RELEASE_NUM)/el5/.
	cp /var/lib/mock/fedora-7-i386/result/* public_html/$(PACKAGE)/$(PACKAGE_VERSION)-$(RELEASE_NUM)/fc7/.
	cp /var/lib/mock/fedora-8-i386/result/* public_html/$(PACKAGE)/$(PACKAGE_VERSION)-$(RELEASE_NUM)/fc8/.
	cp /var/lib/mock/fedora-development-i386/result/* public_html/$(PACKAGE)/$(PACKAGE_VERSION)-$(RELEASE_NUM)/fc9/.
	scp -r public_html fedorapeople.org:.

