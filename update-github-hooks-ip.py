#!/usr/bin/env python3
from _py2with3compatibility import urlopen
from json import loads
from os import system
from sys import exit

ip_file = "/data/sdt/github-hook-meta.txt"
cnt = 0
with open("%s.tmp" % ip_file, "w") as ref:
    for m in [
        i.encode().decode()
        for i in loads(urlopen("https://api.github.com/meta").readlines()[0])["hooks"]
    ]:
        ref.write("%s\n" % m)
        cnt += 1
if cnt:
    system("mv %s.tmp %s" % (ip_file, ip_file))
else:
    system("rm -f %s.tmp %s" % ip_file)
    exit(1)
