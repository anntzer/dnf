#!/usr/bin/python -tt
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Library General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place - Suite 330, Boston, MA 02111-1307, USA.
# Copyright 2004 Duke University

import rpmUtils.miscutils
import rpmUtils.arch
import rpmUtils

class Updates:
    """This class computes and keeps track of updates and obsoletes.
       initialize, add installed packages, add available packages (both as
       unique lists of name, epoch, ver, rel, arch tuples), add an optional dict
       of obsoleting packages with obsoletes and what they obsolete ie:
        foo, i386, 0, 1.1, 1: bar >= 1.1."""

    def __init__(self, instlist, availlist):
        self.changeTup = [] # storage list tuple of updates or obsoletes
                            # (oldpkg, newpkg, ['update'|'obsolete'])

        self.installed = instlist # list of installed pkgs (n, a, e, v, r)
        self.available = availlist # list of available pkgs (n, a, e, v, r)                               
        self.obsoletes = {} # dict of obsoleting package->[what it obsoletes]
        self.exactarch = 1 # don't change archs by default
        self.myarch = rpmUtils.arch.getCanonArch() # this is for debugging only 
                                                   # set this if you want to 
                                                   # test on some other arch
                                                   # otherwise leave it alone
        
        # make some dicts from installed and available
        self.installdict = self.makeNADict(self.installed, 1)
        self.availdict = self.makeNADict(self.available, 1)

        # holder for our updates dict
        self.updatesdict = {}

    def makeNADict(self, pkglist, Nonelists):
        """return lists of (e,v,r) tuples as value of a dict keyed on (n, a)
            optionally will return a (n, None) entry with all the a for that
            n in tuples of (a,e,v,r)"""
            
        returndict = {}
        for (n, a, e, v, r) in pkglist:
            if not returndict.has_key((n, a)):
                returndict[(n, a)] = []
            returndict[(n, a)].append((e,v,r))

            if Nonelists:
                if not returndict.has_key((n, None)):
                    returndict[(n, None)] = []
                returndict[(n, None)].append((a, e, v, r))
            
        return returndict
                    

    def returnNewest(self, evrlist):
        """takes a list of (e, v, r) tuples and returns the newest one"""
        if len(evrlist)==0:
            raise rpmUtils.RpmUtilsError, "Zero Length List in returnNewest call"
            
        if len(evrlist)==1:
            return evrlist[0]
        
        (new_e, new_v, new_r) = evrlist[0] # we'll call the first ones 'newest'
        
        for (e, v, r) in evrlist[1:]:
            rc = rpmUtils.miscutils.compareEVR((e, v, r), (new_e, new_v, new_r))
            if rc > 0:
                new_e = e
                new_v = v
                new_r = r
        return (new_e, new_v, new_r)
         

    def returnHighestVerFromAllArchsByName(self, name, archlist, pkglist):
        """returns a list of package tuples in a list (n, a, e, v, r)
           takes a package name, a list of archs, and a list of pkgs in
           (n, a, e, v, r) form."""
        # go through list and throw out all pkgs not in archlist
        matchlist = []
        for (n, a, e, v, r) in pkglist:
            if name == n:
                if a in archlist:
                    matchlist.append((n, a, e, v, r))

        if len(matchlist) == 0:
            return []
            
        # get all the evr's in a tuple list for returning the highest
        verlist = []
        for (n, a, e, v, r) in matchlist:
            verlist.append((e,v,r))

        (high_e, high_v, high_r) = self.returnNewest(verlist)
            
        returnlist = []
        for (n, a, e, v, r) in matchlist:
            if (high_e, high_v, high_r) == (e, v, r):
                returnlist.append((n,a,e,v,r))
                
        return returnlist               
           
    def condenseUpdates(self):
        """remove any accidental duplicates in updates"""
        
        for tup in self.updatesdict.keys():
            if len(self.updatesdict[tup]) > 1:
                mylist = self.updatesdict[tup]
                self.updatesdict[tup] = rpmUtils.miscutils.unique(mylist)
        
    def doUpdates(self):
        """check for key lists as populated then commit acts of evil to
           determine what is updated and/or obsoleted, populate self.updatesdict
        """
        
        
        # best bet is to chew through the pkgs and throw out the new ones early
        # then deal with the ones where there are a single pkg installed and a 
        # single pkg available
        # then deal with the multiples

        # we should take the whole list as a 'newlist' and remove those entries
        # which are clearly:
        #   1. updates 
        #   2. identical to the ones in ourdb
        #   3. not in our archdict at all
        
        simpleupdate = []
        complexupdate = []
        
        updatedict = {} # (old n, a, e, v, r) : [(new n, a, e, v, r)]
                        # make the new ones a list b/c while we _shouldn't_
                        # have multiple updaters, we might and well, it needs
                        # to be solved one way or the other <sigh>
        newpkgs = []
        newpkgs = self.availdict
        
        archlist = rpmUtils.arch.getArchList(self.myarch)
                
        for (n, a) in newpkgs.keys():
            # remove stuff not in our archdict
            # high log here
            if a is None:
                for (arch, e,v,r) in newpkgs[(n, a)]:
                    if arch not in archlist:
                        newpkgs[(n, a)].remove((arch, e,v,r))
                continue
                
            if a not in archlist:
                # high log here
                del newpkgs[(n, a)]
                continue

        # remove the older stuff - if we're doing an update we only want the
        # newest evrs                
        for (n, a) in newpkgs.keys():
            if a is None:
                continue

            (new_e,new_v,new_r) = self.returnNewest(newpkgs[(n, a)])
            for (e, v, r) in newpkgs[(n, a)]:
                if (new_e, new_v, new_r) != (e, v, r):
                    newpkgs[(n, a)].remove((e, v, r))

                
        for (n, a) in newpkgs.keys():
            if a is None: # the None archs are only for lookups
                continue
           
            # simple ones - look for exact matches or older stuff
            if self.installdict.has_key((n, a)):
                for (rpm_e, rpm_v, rpm_r) in self.installdict[(n, a)]:
                    (e, v, r) = self.returnNewest(newpkgs[(n,a)])
                    rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))
                    if rc <= 0:
                        try:
                            newpkgs[(n, a)].remove((e, v, r))
                        except ValueError:
                            pass

        # get rid of all the empty dict entries:
        for nakey in newpkgs.keys():
            if len(newpkgs[nakey]) == 0:
                del newpkgs[nakey]


        # ok at this point our newpkgs list should be thinned, we should have only
        # the newest e,v,r's and only archs we can actually use
        for (n, a) in newpkgs.keys():
            if a is None: # the None archs are only for lookups
                continue
    
            if self.installdict.has_key((n, None)):
                installarchs = []
                availarchs = []
                for (a, e, v ,r) in newpkgs[(n, None)]:
                    availarchs.append(a)
                for (a, e, v, r) in self.installdict[(n, None)]:
                    installarchs.append(a)

                if len(availarchs) > 1 or len(installarchs) > 1:
                    #log(4, 'putting %s in complex update list' % name)
                    print 'putting %s in complex update' % n
                    complexupdate.append(n)
                else:
                    #log(4, 'putting %s in simple update list' % name)
                    print 'putting %s in simple update' % n
                    simpleupdate.append((n, a))

        # we have our lists to work with now
    
        # simple cases
        for (n, a) in simpleupdate:
            # try to be as precise as possible
            if self.exactarch:
                if self.installdict.has_key((n, a)):
                    (rpm_e, rpm_v, rpm_r) = self.returnNewest(self.installdict[(n, a)])
                    if newpkgs.has_key((n,a)):
                        (e, v, r) = self.returnNewest(newpkgs[(n, a)])
                        rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))
                        if rc > 0:
                            # this is definitely an update - put it in the dict
                            if not updatedict.has_key((n, a, rpm_e, rpm_v, rpm_r)):
                                updatedict[(n, a, rpm_e, rpm_v, rpm_r)] = []
                            updatedict[(n, a, rpm_e, rpm_v, rpm_r)].append((n, a, e, v, r))
    
            else:
                # we could only have 1 arch in our rpmdb and 1 arch of pkg 
                # available - so we shouldn't have to worry about the lists, here
                # we just need to find the arch of the installed pkg so we can 
                # check it's (e, v, r)
                (rpm_a, rpm_e, rpm_v, rpm_r) = self.installdict[(n, None)][0]
                if newpkgs.has_key((n, None)):
                    for (a, e, v, r) in newpkgs[(n, None)]:
                        rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))
                        if rc > 0:
                            # this is definitely an update - put it in the dict
                            if not updatedict.has_key((n, rpm_a, rpm_e, rpm_v, rpm_r)):
                                updatedict[(n, rpm_a, rpm_e, rpm_v, rpm_r)] = []
                            updatedict[(n, rpm_a, rpm_e, rpm_v, rpm_r)].append((n, a, e, v, r))


        # complex cases

        # we're multilib/biarch
        # we need to check the name.arch in two different trees
        # one for the multiarch itself and one for the compat arch
        # ie: x86_64 and athlon(i686-i386) - we don't want to descend
        # x86_64->i686 
        archlists = []
        if rpmUtils.arch.multilibArches.has_key(self.myarch):
            multicompat = rpmUtils.arch.getMultiArchInfo(self.myarch)[0]
            multiarchlist = rpmUtils.arch.getArchList(multicompat)
            archlists = [ [self.myarch], multiarchlist ]
        else:
            archlists = [ archlist ]
            
        for n in complexupdate:
            for thisarchlist in archlists:
                # we need to get the highest version and the archs that have it
                # of the installed pkgs            
                tmplist = []
                for (a, e, v, r) in self.installdict[(n, None)]:
                    tmplist.append((n, a, e, v, r))

                highestinstalledpkgs = self.returnHighestVerFromAllArchsByName(n,
                                         thisarchlist, tmplist)
                                         
                
                tmplist = []
                for (a, e, v, r) in newpkgs[(n, None)]:
                    tmplist.append((n, a, e, v, r))                        
                
                highestavailablepkgs = self.returnHighestVerFromAllArchsByName(n,
                                         thisarchlist, tmplist)

                hapdict = self.makeNADict(highestavailablepkgs, 0)
                hipdict = self.makeNADict(highestinstalledpkgs, 0)

                # now we have the two sets of pkgs
                if self.exactarch:              
                    for (n, a) in hipdict:
                        if hapdict.has_key((n, a)):
                            # we've got a match - get our versions and compare
                            (rpm_e, rpm_v, rpm_r) = hipdict[(n, a)][0] # only ever going to be first one
                            (e, v, r) = hapdict[(n, a)][0] # there can be only one
                            rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))
                            if rc > 0:
                                # this is definitely an update - put it in the dict
                                if not updatedict.has_key((n, a, rpm_e, rpm_v, rpm_r)):
                                    updatedict[(n, a, rpm_e, rpm_v, rpm_r)] = []
                                updatedict[(n, a, rpm_e, rpm_v, rpm_r)].append((n, a, e, v, r))
                else:
                    print 'processing %s' % n
                    # this is where we have to have an arch contest if there
                    # is more than one arch updating with the highest ver
                    instarchs = []
                    availarchs = []
                    for (n,a) in hipdict.keys():
                        instarchs.append(a)
                    for (n,a) in hapdict.keys():
                        availarchs.append(a)
                    
                    rpm_a = rpmUtils.arch.bestArchFromList(instarchs, myarch=self.myarch)
                    a = rpmUtils.arch.bestArchFromList(availarchs, myarch=self.myarch)

                    if rpm_a is None or a is None:
                        continue
                        
                    (rpm_e, rpm_v, rpm_r) = hipdict[(n, rpm_a)][0] # there can be just one
                    (e, v, r) = hapdict[(n, a)][0] # just one, I'm sure, I swear!

                    rc = rpmUtils.miscutils.compareEVR((e, v, r), (rpm_e, rpm_v, rpm_r))

                    if rc > 0:
                        # this is definitely an update - put it in the dict
                        if not updatedict.has_key((n, rpm_a, rpm_e, rpm_v, rpm_r)):
                            updatedict[(n, rpm_a, rpm_e, rpm_v, rpm_r)] = []
                        updatedict[(n, rpm_a, rpm_e, rpm_v, rpm_r)].append((n, a, e, v, r))
                   
                   
        self.updatesdict = updatedict                    
        


# FIX ME
# why do the name='bar' not work but name='foo' do work in the code below
        
    def getUpdatesTuples(self, name=None, arch=None):
        """returns updates for packages in a list of tuples of:
          (updating naevr, installed naevr)"""
        returnlist = []
        for oldtup in self.updatesdict.keys():
            (old_n, old_a, old_e, old_v, old_r) = oldtup
            for newtup in self.updatesdict[oldtup]:
                returnlist.append((newtup, oldtup))
        
        if name:
            for ((n, a, e, v, r), oldtup) in returnlist:
                if name != n:
                    returnlist.remove(((n, a, e, v, r), oldtup))
        if arch:
            for ((n, a, e, v, r), oldtup) in returnlist:
                if arch != a:
                    returnlist.remove(((n, a, e, v, r), oldtup))
                    
        return returnlist            

    def getUpdatesList(self, name=None, arch=None):
        """returns updating packages in a list of (naevr) tuples"""
        mylist = []
        for oldtup in self.updatesdict.keys():
            for newtup in self.updatesdict[oldtup]:
                mylist.append(newtup)
        print mylist
                
        if name is not None:
            for (n, a, e, v, r) in mylist:
                print 'checking'
                if n != name:
                    mylist.remove((n, a, e, v, r))
                    print 'rm %s' % n
                else:
                    print '%s equls %s' % (n, name)
                    
        if arch is not None:
            for (n, a, e, v, r) in mylist:
                if a != arch:
                    mylist.remove((n, a, e, v, r))
                
        return mylist
                
    def getObsoletesTuples(self, name=None, arch=None):
        """returns obsoletes for packages in a list of tuples of:
           (obsoleting naevr, installed naevr)"""
           
    def getObsoletesList(self, name=None, arch=None):
        """returns obsoleting packages in a list of naevr tuples"""

    def getProblems(self):
        """return list of problems:
           - Packages that are both obsoleted and updated.
           - Packages that have multiple obsoletes.
           - Packages that _still_ have multiple updates
        """

             
