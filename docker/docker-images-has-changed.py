#!/usr/bin/env python
from __future__ import print_function
from sys import exit
from docker_utils import has_parent_changed
from argparse import ArgumentParser

parser = ArgumentParser(description="check if docker image based on the same layer(s) as the parent image")
parser.add_argument("--parent_image", type=str, help="Parent docker image")
parser.add_argument("--image", type=str, help="Inherited docker image")
args = parser.parse_args()
if has_parent_changed(args.parent_image, args.image) == True :
  exit(0)
else: 
  exit(1)

