#!/bin/sh -ex

IMAGE_CC7=`openstack image list | grep 'CC7 - x86_64' | awk -F'|' '{print $3}' | sed -e 's/^[[:space:]]*//' | sed -e 's/[[:space:]]*$//'`
IMAGE_SLC6=`openstack image list | grep 'SLC6 - x86_64' | awk -F'|' '{print $3}' | sed -e 's/^[[:space:]]*//' | sed -e 's/[[:space:]]*$//'`
