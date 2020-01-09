#!/usr/bin/env python
from __future__ import print_function
from copy import deepcopy
from github import Github
from os.path import expanduser
from argparse import ArgumentParser
from sys import exit
from socket import setdefaulttimeout
from github_utils import api_rate_limits, github_api,add_organization_member
from categories import CMSSW_L1
setdefaulttimeout(120)

CMS_OWNERS = [ "smuzaffar", "cmsbuild" ] + CMSSW_L1
CMS_SDT    = [ "mrodozov", "tulamor" ]
CMS_ORGANIZATIONS = [ "cms-data", "cms-externals", "cms-sw" ]

REPO_OWNERS = {}
REPO_TEAMS  = {}
for org in CMS_ORGANIZATIONS:
  REPO_OWNERS[org] = CMS_OWNERS[:]
  REPO_TEAMS[org]  = {}

#################################
#Set Extra owners for repos     #
#################################
REPO_OWNERS["cms-data"]      += []
REPO_OWNERS["cms-externals"] += []
REPO_OWNERS["cms-sw"]        += [ "sextonkennedy" ]

#################################
#Set Teams for organizations    #
#################################
#Teams for cms-data
REPO_TEAMS["cms-data"]["Developers"] =  {
  "members"      : CMS_SDT,
  "repositories" : { "*" : "push" }
}

#Teams for cms-externals
REPO_TEAMS["cms-externals"]["Developers"] = deepcopy(REPO_TEAMS["cms-data"]["Developers"])
REPO_TEAMS["cms-externals"]["boost-developers"] = { "members": ["fwyzard"], "repositories" : { "boost" : "push" } }
REPO_TEAMS["cms-externals"]["Developers"]["members"].append("gartung")
REPO_TEAMS["cms-externals"]["Developers"]["members"].append("fwyzard")

#Teams for cms-sw
REPO_TEAMS["cms-sw"]["RecoLuminosity-LumiDB-admins"] = { 
  "members" : [],
  "repositories" : { "RecoLuminosity-LumiDB": "admin"}
}
REPO_TEAMS["cms-sw"]["generators-l2"] = { 
  "members" : ["agrohsje","efeyazgan","qliphy"], 
  "repositories" :  { "genproductions" : "admin",
                      "xsecdb" : "admin"}
}
REPO_TEAMS["cms-sw"]["Dqm-Integration-developers"] = {
  "members" : ["rovere","deguio"],
  "repositories" : { "DQM-Integration": "push"}
}
REPO_TEAMS["cms-sw"]["configdb-owners"] = {
  "members" : ["fwyzard", "Martin-Grunewald", "vinnie87"],
  "repositories" : { "hlt-confdb":"admin", "web-confdb":"admin"}
}
REPO_TEAMS["cms-sw"]["cmsdist-writers"] = {
  "members" : [ "h4d4", "muhammadimranfarooqi" ] + CMS_SDT,
  "repositories" : { "cmsdist":"push" }
}
REPO_TEAMS["cms-sw"]["cmssw-l2"] = {
  "members" : [ "*" ],
  "repositories" : { "cmssw":"pull" }
}
REPO_TEAMS["cms-sw"]["cmssw-developers"] = {
  "members" : [ "*" ],
  "repositories" : { "cmssw":"pull" }
}
REPO_TEAMS["cms-sw"]["cms-sw-writers"] = {
  "members" : CMS_SDT,
  "repositories" : { "*":"push", "!cmssw" : "pull", "!cmsdist" : "pull" }
}
REPO_TEAMS["cms-sw"]["cms-sw-admins"] = {
  "members" : [ "smuzaffar", "tulamor" ],
  "repositories" : { "cmssdt-wiki":"admin" }
}
#################################
parser = ArgumentParser()
parser.add_argument("-o", "--organization", dest="organization", help="Github Organization name e.g. cms-sw. Default is * i.e. all cms origanizations", type=str, default="*")
parser.add_argument("-n", "-dry-run", dest="dryRun", default=False, action="store_true")
args = parser.parse_args()

GH_TOKEN = open(expanduser("~/.github-token")).read().strip()
gh = Github(login_or_token=GH_TOKEN)
cache = {"users" : {}}
total_changes=0
err_code=0
for org_name in CMS_ORGANIZATIONS:
  if args.organization!="*" and org_name!=args.organization: continue
  print("Wroking on Organization ",org_name)
  api_rate_limits(gh)
  org = gh.get_organization(org_name)
  ok_mems = []
  print("  Looking for owners:",REPO_OWNERS[org_name])
  chg_flag=0
  for mem in org.get_members(role="admin"):
    login = mem.login.encode("ascii", "ignore")
    if not login in cache["users"]: cache["users"][login] = mem
    if not login in REPO_OWNERS[org_name]:
      if not args.dryRun: add_organization_member(GH_TOKEN, org_name, login, role="member")
      print("    =>Remove owner:",login)
      chg_flag+=1
    else:
      ok_mems.append(login)
  for login in [ l for l in REPO_OWNERS[org_name] if not l in ok_mems ]:
    if not args.dryRun: add_organization_member(GH_TOKEN, org_name, login, role="admin")
    print("    =>Add owner:",login)
    chg_flag+=1
  total_changes+=chg_flag
  if not chg_flag: print("    OK Owners")
  print("  Looking for teams:",list(REPO_TEAMS[org_name].keys()))
  org_repos =  [ repo for repo in org.get_repos() ]
  for team in org.get_teams():
    print("    Checking team:",team.name)
    api_rate_limits(gh,msg=False)
    team_info = {}
    try: team_info = REPO_TEAMS[org_name][team.name]
    except:
      print("    WARNING: New team found on Github:",team.name)
      err_code=1
      continue
    members = team_info["members"]
    tm_members = [ mem for mem in team.get_members()]
    tm_members_login = [ mem.login.encode("ascii", "ignore") for mem in tm_members ]
    print("      Valid Members:",members)
    print("      Existing Members:",tm_members_login)
    ok_mems = ["*"]
    chg_flag=0
    if not "*" in members:
      for mem in tm_members:
        api_rate_limits(gh,msg=False)
        login = mem.login.encode("ascii", "ignore")
        if not login in cache["users"]: cache["users"][login] = mem
        if (login in members) or ("*" in members):
          ok_mems.append(login)
        else:
          if not args.dryRun: team.remove_from_members(mem)
          print("      =>Removed member:",login)
          chg_flag+=1
      for login in [ l for l in members if not l in ok_mems ]:
        api_rate_limits(gh,msg=False)
        if not login in cache["users"]: cache["users"][login] = gh.get_user(login)
        if not args.dryRun:
          try: team.add_to_members(cache["users"][login])
          except Exception as e:
            print(e)
            err_code=1
        print("      =>Added member:",login)
        chg_flag+=1
    total_changes+=chg_flag
    if not chg_flag: print("      OK Team members")
    team_repos      = [ repo for repo in team.get_repos() ]
    team_repos_name = [ repo.name.encode("ascii", "ignore") for repo in team_repos ]
    print("      Checking team repositories")
    print("        Valid Repos:",list(team_info["repositories"].keys()))
    print("        Existing Repos:",team_repos_name)
    repo_to_check = team_repos_name[:]
    for repo in team_info["repositories"]:
      if repo=="*":              repo_to_check += [ r.name.encode("ascii", "ignore") for r in org_repos ]
      elif repo.startswith("!"): repo_to_check += [repo[1:]]
      else:                      repo_to_check += [repo]
    chg_flag=0
    for repo_name in set(repo_to_check):
      api_rate_limits(gh, msg=False)
      inv_repo = "!"+repo_name
      repo = [ r for r in team_repos if r.name.encode("ascii", "ignore") == repo_name ]
      if (repo_name in team_info["repositories"]) or \
         ("*" in team_info["repositories"] and (not inv_repo in team_info["repositories"])):
         prem = "pull"
         if repo_name in team_info["repositories"]: prem = team_info["repositories"][repo_name]
         elif "*" in team_info["repositories"]: prem = team_info["repositories"]["*"]
         if not repo_name in team_repos_name:
           if not args.dryRun:
             if not repo: repo.append(gh.get_repo(org_name+"/"+repo_name))
             team.set_repo_permission(repo[0], prem)
           print("        =>Added repo:",repo_name,prem)
           chg_flag+=1
         else:
           curperm = repo[0].permissions
           set_perm=False
           curperm_name="pull"
           if curperm.admin:
             curperm_name="admin"
             if not prem=="admin": set_perm=True
           elif curperm.push:
             curperm_name="push"
             if not prem=="push": set_perm=True
           elif curperm.pull:
             if not prem=="pull": set_perm=True
           if set_perm:
             if not args.dryRun:
               if not repo: repo.append(gh.get_repo(org_name+"/"+repo_name))
               team.set_repo_permission(repo[0], prem)
             print("        =>Set Permission:",repo_name,curperm_name,"=>",prem)
             chg_flag+=1
      elif repo_name in team_repos_name:
        if not args.dryRun:
          if not repo: repo.append(gh.get_repo(org_name+"/"+repo_name))
          team.remove_from_repos(repo[0])
        print("        =>Removed repository:",repo_name)
        chg_flag+=1
    if not chg_flag: print("        OK Team Repositories")
    total_changes+=chg_flag
print("Total Updates:",total_changes)
exit(err_code)
