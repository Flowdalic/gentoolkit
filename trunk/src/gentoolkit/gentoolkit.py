#! /usr/bin/env python2.2
#
# Copyright 2003 Karl Trygve Kalleberg
# Copyright 2003 Gentoo Technologies, Inc.
# Distributed under the terms of the GNU General Public License v2
#
# $Header$
# Author: Karl Trygve Kalleberg <karltk@gentoo.org>
#
# Portions written ripped from etcat, written by Alistair Tse <liquidx@gentoo.org>

__author__ = "Karl Trygve Kalleberg"
__email__ = "karltk@gentoo.org"
__version__ = "0.1.0"
__productname__ = "gentoolkit"
__description__ = "Gentoolkit Common Library"

import os
import portage
import re
import string

settings = portage.settings
porttree = portage.db[portage.root]["porttree"]
vartree  = portage.db[portage.root]["vartree"]
virtuals = portage.db[portage.root]["virtuals"]

# Nomenclature:
#
# CPV - category/package-version

class Package:
    """Package descriptor. Contains convenience functions for querying the
    state of a package, its contents, name manipulation, ebuild info and
    similar."""
    def __init__(self,cpv):
        self._cpv=cpv
        self._scpv=portage.catpkgsplit(self._cpv)
        self._db=None
    def get_name(self):
        """Returns base name of package, no category nor version"""
        return self._scpv[1]
    def get_version(self):
        """Returns version of package, with revision number"""
        v=self._scpv[2]
        if self._scpv[3] != "r0":
            v+="-"+self._scpv[3]
        return v
    def get_category(self):
        """Returns category of package"""
        return self._scpv[0]
    def get_cpv(self):
        """Returns full Category/Package-Version string"""
        return self._cpv
    def get_provides(self):
        """Return a list of provides, if any"""
        return vartree.get_provides(self._cpv)
    def get_dependants(self):
        """Retrieves a list of CPVs for all packages depending on this one"""
        raise "Not implemented yet!"
    def get_runtime_deps(self):
        """Returns a linearised list of first-level compile time dependencies for this package, on
        the form [(comparator, [use flags], cpv), ...]"""
        cd=self.get_env_var("RDEPEND").split()
        r,i=self._parse_deps(cd)
        return r
    def get_compiletime_deps(self):
        """Returns a linearised list of first-level compile time dependencies for this package, on
        the form [(comparator, [use flags], cpv), ...]"""
        rd=self.get_env_var("DEPEND").split()
        r,i=self._parse_deps(rd)
        return r
    def _parse_deps(self,deps,curuse=[],level=0):
        # store (comparator, [use predicates], cpv)
        r=[]
        comparators=["~","<",">","=","<=",">="]
        end=len(deps)
        i=0
        while i < end:
            tok=deps[i]
            if tok == ')':
                return r,i
            if tok[-1] == "?" or tok[0] == "!":
                tok=tok.replace("?","")
                sr,l = self._parse_deps(deps[i+2:],curuse=curuse+[tok],level=level+1)
                r += sr
                i+=l+3
                continue
            # pick out comparator, if any
            cmp=""
            for c in comparators:
                if tok.find(c) == 0:
                    cmp=c
            tok=tok[len(cmp):]
            r.append((cmp,curuse,tok))
            i+=1
        return r,i
    def is_installed(self):
        """Returns true if this package is installed (merged)"""
        self._initdb()
        return os.path.exists(self._db.getpath())
    def is_overlay(self):
        dir,ovl=portage.portdb.findname2(self._cpv)
        return ovl
    def is_masked(self):
        """Returns true if this package is masked against installation. Note: We blindly assume that
        the package actually exists on disk somewhere."""
        unmasked = portage.portdb.xmatch("match-visible", "=" + self._cpv)
        return self._cpv not in unmasked
    def get_ebuild_path(self,in_vartree=0):
        """Returns the complete path to the .ebuild file"""
        if in_vartree:
            return vartree.getebuildpath(self._cpv)
        else:
            return portage.portdb.findname(self._cpv)
    def get_package_path(self):
        """Returns the path to where the ChangeLog, Manifest, .ebuild files reside"""
        p=self.get_ebuild_path()
        sp=p.split("/")
        if len(sp):
            return string.join(sp[:-1],"/")
    def get_env_var(self, var):
        """Returns one of the predefined env vars DEPEND, RDEPEND, SRC_URI,...."""
        r=vartree.dbapi.aux_get(self._cpv,[var])
        if not r:
            raise "WTF??"
        if len(r)!=1:
            raise "Should only get one element!"
        return r[0]
    def get_use_vars(self):
        """Returns the USE flags active at time of installation"""
        self._initdb()
        if self.is_installed():
            return self._db.getfile("USE")
        return ""
    def get_contents(self):
        """Returns the full contents, as a dictionary, on the form
        [ '/bin/foo' : [ 'obj', '1052505381', '45ca8b8975d5094cd75bdc61e9933691' ], ... ]"""
        self._initdb()
        if self.is_installed():
            return self._db.getcontents()
        return {}        
    def compare_version(self,other):
        """Compares this package's version to another's CPV; returns -1, 0, 1"""
        v1=self._scpv
        v2=portage.catpkgsplit(other)
        if v1[0] != v2[0] or v1[1] != v2[1]:
            return None
        return portage.pkgcmp(v1[1:],v2[1:])
    def size(self):
        """Estimates the installed size of the contents of this package, if possible.
        Returns [size, number of files in total, number of uncounted files]"""
        contents = self.get_contents()
        size=0
        uncounted = 0
        files=0
        for x in contents:
            try:
                size += os.stat(x).st_size
                files += 1
            except OSError:
                uncounted += 1
        return [size, files, uncounted]

    def _initdb(self):
        """Internal helper function; loads package information from disk,
        when necessary"""
        if not self._db:
            cat=self.get_category()
            pnv=self.get_name()+"-"+self.get_version()
            self._db=portage.dblink(cat,pnv,"")

#
# Global helper functions
#

def find_packages(search_key):
    """Returns a list of Package objects that matched the search key."""
    # FIXME: this one failes if search_key contains version suffix
    t=portage.portdb.match(search_key)
    return map(lambda x: Package(x), t)

def find_best_match(search_key):
    """Returns a Package object for the best available installed candidate that
    matched the search key. Doesn't handle virtuals perfectly"""
    # FIXME: How should we handled versioned virtuals??
    cat,pkg,ver,rev=split_package_name(search_key)
    if cat == "virtual":
        t=vartree.dep_bestmatch(cat+"/"+pkg)
    else:
        t=vartree.dep_bestmatch(search_key)
    if t:
        return Package(t)
    return None

def find_all_installed_packages(prefilter=None):
    """Returns a list of all installed packages, after applying the prefilter
    function"""
    t=vartree.getallcpv()
    if prefilter:
        t=filter(prefilter,t)
    return map(lambda x: Package(x), t)
    
    return find_all_packages(prefilter,1)

def find_all_packages(prefilter=None):
    """Returns a list of all known packages, installed or not, after applying
    the prefilter function"""
    t=portage.portdb.cp_all()
    if prefilter:
        t=filter(prefilter,t)
    t2=[]
    for x in t:
        t2 += portage.portdb.cp_list(x)
    return map(lambda x: Package(x), t2)

def split_package_name(name):
    """Returns a list on the form [category, name, version, revision]. Revision will
    be 'r0' if none can be inferred. Category and version will be empty, if none can
    be inferred."""
    r=portage.catpkgsplit(name)
    if not r:
        r=name.split("/")
        if len(r) == 1:
            return ["",name,"","r0"]
        else:
            return r + ["","r0"]
    if r[0] == 'null':
        r[0] = ''
    return r

if __name__ == "__main__":
    print "This module is for import only"

# - get dependencies
# - walk dependency tree

