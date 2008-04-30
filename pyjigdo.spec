%{!?python_sitelib: %define python_sitelib %(python -c "from distutils.sysconfig import get_python_lib; print get_python_lib()")}

Summary:        Python version of Jigdo, slightly modified
Name:           pyjigdo
Version:        0.3.0
Release:        2%{?dist}
License:        GPLv2+
Group:          Applications/System
URL:            https://hosted.fedoraproject.org/projects/pyjigdo
Source0:        http://files.pyjigdo.fedoraunity.org/%{name}-%{version}.tar.gz
BuildRoot:      %{_tmppath}/%{name}-%{version}-%{release}-root-%(%{__id_u} -n)
BuildArch:      noarch
BuildRequires:  intltool, gettext, python
Requires:	python, rhpl, python-urlgrabber, jigdo, fuseiso

%description
PyJigdo is a Python rewrite of the popular Jigdo distribution framework. It has
also been slightly modified to add some extra features.

%prep
%setup -q

%build
%configure
make

%install
rm -rf $RPM_BUILD_ROOT
make install DESTDIR=$RPM_BUILD_ROOT

%clean
rm -rf $RPM_BUILD_ROOT

%files
%defattr(-,root,root,-)
%doc README NEWS AUTHORS COPYING TODO
%doc %{_mandir}/man1/*
%doc %{_mandir}/man5/*
%doc %{_mandir}/man8/*
%{python_sitelib}/pyjigdo/
%{_bindir}/*
%dir %{_sysconfdir}/pyjigdo
%config(noreplace) %{_sysconfdir}/pyjigdo/pyjigdo.conf

%changelog
* Wed Apr 30 2008 Jason Farrell <farrellj a gmail.com> 0.3.0-2
- Added pyjigdo.1 manpage

* Thu Apr 24 2008 Jonathan Steffan <jon a fedoraunity.org> 0.3.0-1
- Update Requires for fuseiso
- Update to version 0.3.0
- This release is a complete rewrite, too much to list here

* Wed Dec 19 2007 Jonathan Steffan <jon a fedoraunity.org> 0.2-3
- Remove gitdate

* Tue Dec 11 2007 Jonathan Steffan <jon a fedoraunity.org> 0.2-2.20071211git
- Rebuild for review ticket

* Tue Nov 27 2007 Stewart Adam <s.adam a diffingo.com> 0.2-2.20071127git
- Fix %%changelog date, drop automatic gitdate

* Fri Nov 23 2007 Stewart Adam <s.adam a diffingo.com> 0.2-2.20071123git
- Use gitdate

* Wed Oct 10 2007 Stewart Adam <s.adam a diffingo.com> 0.2-1
- Split up py files
- License change from GPLv2 to GPLv2+
- Make __init__.py's __version__ work based on automake

* Tue Oct 09 2007 Jonathan Steffan <jon a fedoraunity.org> 0.1-2
- Updated spec to build for alpha test release

* Sun Oct 07 2007 Jonathan Steffan <jon a fedoraunity.org> 0.1-1
- Initial spec

