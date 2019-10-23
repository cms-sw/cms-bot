from __future__ import print_function
from github import Github
from optparse import OptionParser
import repo_config
from os.path import expanduser
from urllib2 import urlopen

def update_tag_version(current_version=None):
    updated_version = None
    if current_version:
        updated_version=str(int(current_version)+1)
        if len(updated_version) == 1:
            updated_version = '0'+updated_version

    return updated_version

if __name__ == "__main__":

  parser = OptionParser(usage="%prog <cms-data-repo> <cms-dist repo> <pull-request-id>")

  parser.add_option("-r", "--data-repo", dest="data_repo", help="Github data repositoy name e.g. cms-data/RecoTauTag-TrainingFiles.",
                    type=str, default=None)
  parser.add_option("-d", "--dist-repo", dest="dist_repo", help="Github dist repositoy name e.g. cms-sw/cmsdist.",
                    type=str, default='')
  parser.add_option("-p", "--pull-request", dest="pull_request", help="Pull request number",
                    type=str, default=None)
  opts, args = parser.parse_args()

  gh = Github(login_or_token=open(expanduser(repo_config.GH_TOKEN)).read().strip())

  data_repo = gh.get_repo(opts.data_repo)
  data_prid = int(opts.pull_request)
  dist_repo = gh.get_repo(opts.dist_repo)
  data_repo_pr = data_repo.get_pull(data_prid)

  if not data_repo_pr.merged:
      print('Branch has not been merged !')
      exit(0)

  last_release_tag = None
  releases = data_repo.get_releases()
  for i in releases:
      last_release_tag = (i.tag_name)
      break

  if last_release_tag:
    comparison = data_repo.compare('master', last_release_tag)
    print('commits behind ', comparison.behind_by)
    create_new_tag = True if comparison.behind_by > 0 else False # last tag and master commit difference
    print('create new tag ? ', create_new_tag)
  else:
    create_new_tag = True
    last_release_tag = "V00-00-00"

  # if created files and modified files are the same count, all files are new

  response = urlopen(data_repo_pr.patch_url)
  files_created = response.read().count('create mode ')
  files_modified = data_repo_pr.changed_files
  only_new_files=True if files_created == files_modified else False

  # if the latest tag/release compared with master(base) or the pr(head) branch is behind then make new tag
  new_tag = last_release_tag # in case the tag doesnt change
  if create_new_tag:
      nums_only = last_release_tag.strip('V').split('-')
      first, sec, thrd = tuple(nums_only)
      print(first, sec, thrd)
      # update minor for now
      if only_new_files:
          thrd = update_tag_version(thrd)
          print('new files only. update third part: ', thrd)
      else:
          sec = update_tag_version(sec)
          thrd = '00'
          print('files were modified, update mid version and reset minor', sec, thrd)
      new_tag = 'V'+first+'-'+sec+'-'+thrd
      # message should be referencing the PR that triggers this job
      new_rel = data_repo.create_git_release(new_tag, new_tag, 'Details in: '+data_repo_pr.html_url, False, False)

  last_release_tag = None
  releases = data_repo.get_releases()
  for i in releases:
      last_release_tag = i.tag_name
      break

  default_cms_dist_branch = dist_repo.default_branch
  repo_name_only = opts.data_repo.split('/')[1]
  repo_tag_pr_branch = 'update-'+repo_name_only+'-to-'+last_release_tag

  sb = dist_repo.get_branch(default_cms_dist_branch)
  dest_branch = None #

  try:
      dist_repo.create_git_ref(ref='refs/heads/' + repo_tag_pr_branch, sha=sb.commit.sha)
      dest_branch = dist_repo.get_branch(repo_tag_pr_branch)
  except Exception as e:
      print(str(e))
      dest_branch = dist_repo.get_branch(repo_tag_pr_branch)
      print('Branch exists')

  # file with tags on the default branch
  cmsswdatafile = "/data/cmsswdata.txt"
  content_file = dist_repo.get_contents(cmsswdatafile, repo_tag_pr_branch)
  cmsswdatafile_raw = content_file.decoded_content
  new_content = ''
  # remove the existing line no matter where it is and put the new line right under default

  count = 0 # omit first line linebreaker
  for line in cmsswdatafile_raw.splitlines():
      updated_line = None
      if '[default]' in line:
          updated_line = '\n'+line+'\n'+repo_name_only+'='+new_tag+''
      elif repo_name_only in line:
          updated_line = ''
      else:
          if count > 0:
              updated_line = '\n'+line
          else:
              updated_line = line
      count=count+1
      new_content = new_content+updated_line

  mssg = 'Update tag for '+repo_name_only+' to '+new_tag
  update_file_object = dist_repo.update_file(cmsswdatafile, mssg, new_content, content_file.sha, repo_tag_pr_branch)

  # file with tags on the default branch
  cmsswdataspec = "/cmsswdata.spec"
  content_file = dist_repo.get_contents(cmsswdataspec, repo_tag_pr_branch)
  cmsswdatafile_raw = content_file.decoded_content
  new_content = []
  data_pkg = 'data-'+repo_name_only
  flag = 0
  for line in cmsswdatafile_raw.splitlines():
      new_content.append(line)
      if flag==0:
        if data_pkg in line:
          flag = 2
          break
        if line.startswith('Requires: '):
          flag=1
          new_content.append('Requires: '+data_pkg)

  if flag==1:
    mssg = 'Update cmssdata spec for '+data_pkg
    update_file_object = dist_repo.update_file(cmsswdataspec, mssg, '\n'.join(new_content), content_file.sha, repo_tag_pr_branch)

  title = 'Update tag for '+repo_name_only+' to '+new_tag
  body = 'Move '+repo_name_only+" data to new tag, see \n" + data_repo_pr.html_url + '\n'
  change_tag_pull_request = dist_repo.create_pull(title=title, body=body, base=default_cms_dist_branch, head=repo_tag_pr_branch)
