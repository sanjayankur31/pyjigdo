etcconfdir = $(sysconfdir)/pyjigdo/
etcconf_DATA = pyjigdo.conf

#desktopdatadir = $(datadir)/applications/
#desktopdata_DATA = pyjigdo.desktop

PYJIGDOCONFIG = \
	pyjigdo.conf 
#	pyjigdo.desktop

EXTRA_DIST = \
	$(PYJIGDOCONFIG)

install-data-local:
	$(mkinstalldirs) $(DESTDIR)$(sysconfdir)/pam.d
	$(mkinstalldirs) $(DESTDIR)$(sysconfdir)/security/console.apps/
#	$(INSTALL) -m 644 pyjigdo.pam $(DESTDIR)$(sysconfdir)/pam.d/pyjigdo
#	$(INSTALL) -m 644 pyjigdo.console $(DESTDIR)$(sysconfdir)/security/console.apps/pyjigdo

uninstall-local:
	rm -f $(DESTDIR)$(sysconfdir)/pam.d/pyjigdo
	rm -f $(DESTDIR)$(sysconfdir)/security/console.apps/pyjigdo
#	rm -f $(DESTDIR)$(datadir)/applications/pyjigdo.desktop

clean:
	rm -f *~
