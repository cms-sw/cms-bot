#!/usr/bin/env python

# A script to generate the list of releases to deprecate, via a set of regexp.
# TODO unused
from __future__ import print_function
from _py2with3compatibility import urlopen
from xml.sax import make_parser, handler
import re
from optparse import OptionParser
from json import load

INCIPIT = """
Hi All,

Below are the lists of releases which are being proposed to be deprecated.  If you
would like any on this list kept please email me (and NOT post to this
announcement-only HyperNews forum) the following information so we can give it
the correct consideration:

1. Release

2. Reason to keep it

3. Reason you are unable to move to the latest releases in the cycle (as we
expect you should be able to, for example from 3_8_6 to 3_8_7_patch2)

4. When it can be removed

In a week I will repost the final list to be deprecated. They will not
be removed for at least another week after that.

--
Ciao,
Giulio
"""

WHITELIST = ["CMSSW_5_2_7_hltpatch1"]

class ReleasesDeprecator(handler.ContentHandler):
  def __init__(self, whitelist):
    self.whitelist = whitelist
    self.survival = []
    self.devel_deprecated = []
    self.prod_deprecated = []
    self.rules = ["3_[0-9]_[0-9].*", "[45]_[0-9]_[0-9]+.*pre[0-9].*", "6_1_[0-9]+.*pre[0-9].*", "6_2_0_.*pre[0-3]", "4_3_.*", ".*_TS.*", 
                  "CMSSW_[45]_.*cand.*", "5_2_[0-8].*", "5_[0-1]_.*",
                  "5_3_11_patch[1-5]", "4_4_5_patch[1-4]", "5_3_2_patch[1-4]", "5_3_7_patch[1-6]", "6_0_.*", "6_2_0_p1_gcc481",
                  "4_2_.*SLHC.*", "4_2_8_p7rootfix", "5_3_1[2-3]_patch[1-2]", "4_2_4_g94p03c",
                  "5_3_[8-9]_patch[1-2]", "6_1_0", "4_4_2_p10JEmalloc", "6_1_2_SLHC[1357].*", "6_2_0_SLHC[12].*", "5_3_3_patch[12]"]

  def startElement(self, name, attrs):
    if not name == "project":
      return
    release = attrs["label"]
    prod = attrs["type"]
    if release in self.whitelist:
      self.survival.append(release)
      return
    for r in self.rules:
      rule = "CMSSW_" + r
      if re.match(rule, release) and prod == "Development":
        self.devel_deprecated.append(release)
        return
      if re.match(rule, release) and prod == "Production":
        self.prod_deprecated.append(release)
        return
    self.survival.append(release)


if __name__ == "__main__":
  parser = OptionParser()
  parser.add_option("--exclude", "-e", 
                    help="Contents of https://cms-pdmv.cern.ch/mcm/search/?db_name=campaigns&page=-1",
                    dest="exclude_list", default=None)
  opts, args = parser.parse_args()
  whitelist = set()
  if opts.exclude_list:
    exclude_list = load(open(opts.exclude_list))
    excludedReleases = set([x["cmssw_release"] for x in exclude_list["results"]]).union(WHITELIST)
    excludedBaseReleases = set([re.sub("_[a-zA-Z0-9]*patch[0-9]*", "", x) for x in excludedReleases])
    whitelist = excludedBaseReleases.union(excludedReleases)
    print(whitelist)
  releases = urlopen("https://cmstags.cern.ch/tc/ReleasesXML?anytype=1")
  parser = make_parser()
  handler = ReleasesDeprecator(whitelist)
  parser.setContentHandler(handler)
  parser.parse(releases)
  print(INCIPIT)
  print("\n\n# The following **production** releases will be removed:\n\n%s" % "\n".join(sorted(handler.prod_deprecated)))
  print("\n\n# The following **development** releases will be removed:\n\n%s" % "\n".join(sorted(handler.devel_deprecated)))
  print("\n\n# The following releases will be untouched:\n\n%s" % "\n".join(sorted(handler.survival)))
