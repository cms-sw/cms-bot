#! /usr/bin/env python

from __future__ import print_function
from _py2with3compatibility import run_cmd
import re

#
# Interprets the commit history of a branch as a graph.
# It uses git log --graph to do so
# 
# Node: a merge commit, it can be a pull request or a automated merge
#       Each node contains the links to its parent commits and children commits
# 

INFO_SEPARATOR = '--INFO--'
REPO = 'cmssw.git'
MAGIC_COMMAND_GRAPH = 'GIT_DIR='+REPO+' git log --merges --graph --pretty=\'"'+INFO_SEPARATOR+'%H,%s"\' RELEASE_QUEUE '
# This regular expression allows to identify if a merge commit is an automatic forward port
AUTO_FORWARD_PORT_REGEX='Merge CMSSW.+ into CMSSW.+'

#
# load the graph for a given release queue
# maxNodes limits the number of nodes(commits) to check, -1 means no maximum
#
def load_graph(release_queue , maxNodes):
  command = MAGIC_COMMAND_GRAPH.replace('RELEASE_QUEUE',release_queue)

  error, out = run_cmd(command)

  prev_node_lane = {}

  previous_lane = 1
  node_number = 0

  all_nodes = {}

  for line in out.splitlines():
    if maxNodes != -1 and node_number > maxNodes:
      identify_automated_merges(all_nodes)
      return all_nodes
    #check if the line contains a node
    if INFO_SEPARATOR in line:
      
      node_number += 1
      line_parts = line.split(INFO_SEPARATOR)
      lanes = line_parts[0].replace('"','').replace(' ','')
      lane = lanes.index('*') + 1
      
      node_info = line_parts[1]
      node_info_parts = node_info.split(",")
      
      #hash, description
      new_node = Node(node_info_parts[0],node_info_parts[1],lane)
      all_nodes[node_info_parts[0]] = new_node

      # for the first node I just add it without any conection
      if node_number == 1:
        set_previous_node_lane( prev_node_lane , lane , new_node )
        continue

      #changed lane?
      if previous_lane < lane:
        #connect this node with the preivous one from the previous lane
        previous_node = get_previous_node_lane( prev_node_lane , previous_lane )
      else:
        #connect this node with the previous one from of the same lane
        previous_node = get_previous_node_lane( prev_node_lane , lane )

      if previous_node == None:
        set_previous_node_lane( prev_node_lane , lane , new_node )
        previous_lane = lane
        continue

      link_nodes( new_node , previous_node )
      set_previous_node_lane( prev_node_lane , lane , new_node )


      all_nodes[node_info_parts[0]] = new_node
      previous_lane = lane



  identify_automated_merges(all_nodes)

  return all_nodes

#
# adds the node to the prev_node_lane structure in the given lane
#
def set_previous_node_lane( prev_node_lane , lane , node ):
  prev_node_lane[lane] =  node
  #print prev_node_lane

#
# get the previous node for the lane given as parameter
#
def get_previous_node_lane( prev_node_lane , lane ):
  return prev_node_lane.get(lane)

#
# links a parent node with a son node
# parent and son must be instances of Node
#
def link_nodes( parent, son):
  parent.add_son(son)
  son.add_parent(parent)

#
# identifies the automated merge commits that were responsible for bringing 
# a commit into the release queue
#
def identify_automated_merges(nodes):
  commits_from_merge = [n for n in list(nodes.values()) if n.is_from_merge]
  
  for commit in commits_from_merge:
    if not commit.brought_by:
      responsible_commit = identify_responsible_automated_merge(commit)
      commit.brought_by = responsible_commit
      if commit.brought_by:
        responsible_commit.brought_commits.append( commit )
  

  #print '-'.join( [ '%s by %s' % (c.hash,c.brought_by.hash) for c in commits_from_merge if c.brought_by] )

  # automated_merges = [n for n in list(nodes.values()) if n.is_automated_merge]

  #for auto_merge in automated_merges:
  #  auto_merge.printme()


#
# identifies the automated merge that was responsible for binging the commit
#
def identify_responsible_automated_merge(commit):
  children = list(commit.children.values())
  
  if len( children ) == 0:
    return commit

  #for the moment a commit only has one kid! if that changes this needs to be changed
  child = children[0]
  if child.lane == 1:
    return child
  else:
    return identify_responsible_automated_merge(child)  

#
# returns a list of commits(Nodes) of the pull requests that come from a merge commit
#
def get_prs_from_merge_commit( graph ):
  return [ c for c in list(graph.values()) if c.is_from_merge and c.is_pr ] 

#
# returns a list of pr numbers that were brougth by a commit given its hash
#
def get_prs_brought_by_commit( graph , commit_hash ):
  return [ c for c in list(graph.values()) if c.is_pr and c.is_from_merge and c.brought_by.hash == commit_hash ]


class Node(object):
  
  # initializes the node with a hash, the lane (line in history), and a description
  def __init__(self, hash, desc,lane):
    self.hash = hash
    self.desc = desc
    self.lane = lane
    self.is_from_merge = lane > 1
    self.is_automated_merge = re.match(AUTO_FORWARD_PORT_REGEX, desc) != None
    # which commit brought this one to the release queue
    self.brought_by = None 
    # which commits did this commit bring
    self.brought_commits = []
    self.is_pr = 'Merge pull request #' in desc
    
    if self.is_pr:
      self.pr_number = self.identify_pr_number()
    else:
      self.pr_number = None

    # nodes to which is node is parent
    self.children = {}
    # nodes to which this node is son
    self.parents = {}

  def add_son( self , son_node ):
    self.children[son_node.hash] = son_node

  def add_parent(self,parent_node):
    self.parents[parent_node.hash] = parent_node

  def identify_pr_number(self):
    return self.desc.split(' ')[3].replace('#','')

  def printme(self):
    spaces = '' 
    for l in range(self.lane-1):
      spaces += ' '

    print('%s %d;%s-%s' % (spaces,self.lane,self.hash,self.desc))
    print('parents: %s'% '-'.join(list(self.parents.keys())))
    print('children: %s'% '-'.join(list(self.children.keys())))
    print('is automated merge: %s' % self.is_automated_merge)
    print('is from merge commit: %s' % self.is_from_merge)
    print('is pr: %s' % self.is_pr) 
    print('pr number: %s' % self.pr_number)
    if self.is_automated_merge:
      print('Is responsible for: ')
      print(' - '.join([ c.hash for c in self.brought_commits ]))
      print()
      print()
    if self.is_from_merge:
      print('brought by: ')
      print(self.brought_by.hash)



#
# Testing
#
# graph = load_graph('CMSSW_7_2_X',1000)

