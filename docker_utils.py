#!/usr/bin/env python
from __future__ import print_function
from json import loads
from _py2with3compatibility import run_cmd

def get_docker_token(repo):
  print('\nGetting docker.io token ....')
  e, o = run_cmd('curl --silent --request "GET" "https://auth.docker.io/token?service=registry.docker.io&scope=repository:%s:pull"' % repo)
  return loads(o)['token']

def get_docker_image_manifest(repo, tag):
  token = get_docker_token(repo)
  print('Getting image_manifest for %s/%s' % (repo, tag))
  e, o = run_cmd('curl --silent --request "GET" --header "Authorization: Bearer %s" "https://registry-1.docker.io/v2/%s/manifests/%s"' % (token, repo, tag))
  image_manifest=loads(o)
  fsLayers=image_manifest['fsLayers']
  list_of_digests = []
  print('echo fsLayers of %s:%s: \n' % (repo, tag))
  for a in fsLayers:
    print(a)
  return fsLayers

def has_parent_changed(parent_image, cms_image):
  parent_image_list = get_docker_image_manifest(*parent_image.split(':'))
  cms_image_list = get_docker_image_manifest(*cms_image.split(':'))
  while parent_image_list:
    if cms_image_list.pop() != parent_image_list.pop():
      return False
  return True
