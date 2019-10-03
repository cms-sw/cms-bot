#!/usr/bin/env python
from __future__ import print_function
from docker_utils import has_parent_changed
import argparse

parser = argparse.ArgumentParser(description="check if cms docker image based on the same layer(s) as the parent image")
parser.add_argument("parent_image", type=str, help="Parent docker image")
parser.add_argument("cms_image", type=str, help="CMS docker image")
args = parser.parse_args()
has_parent_changed(args.parent_image, args.cms_image)
