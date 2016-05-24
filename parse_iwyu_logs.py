#!/bin/env python
import sys , json
fd=open(sys.argv[1],'r')
splitline = sys.argv[2] + '/src/'
print """<!DOCTYPE html>
<html>
<head>
<style>
table, th, td {
    border: 2px solid green;
    border-collapse: collapse;
}
th, td {
    padding: 5px;
    text-align: left;
}
</style>
</head>"""
print '<a href='+'"'+ sys.argv[1].split('/')[-1] + '"' + '>' + 'Access BuildLog' + '</a><br/>'
print '<table  align="center">'
for l in fd:
  if 'remove these lines' in l:
    line=sec.next()
    line=line.rstrip()
    if len(line):
      print '<tr><td bgcolor="#00FFFF"><h2>'+ l.split(splitline)[-1] +'</h2>'
      while len(line):
        line=line.replace('<','&#60;')
        line=line.replace('>','&#62;')
        #line=line.replace('"','')
        #line=line.replace('- #include ','')
        print '<br/>'+line
        line=sec.next()
        line=line.rstrip()
      print '</td></tr>'
      
  elif 'add these lines' in l:
    sec=iter(fd)
    line=sec.next()
    line=line.rstrip()
    if len(line):
      print '<tr><td bgcolor="#00FF90"><h2>'+ l.split(splitline)[-1]+'</h2>'
      while len(line):
        line=line.replace('<','&#60;')
        line=line.replace('>','&#62;')
        #line=line.replace('#include ','').replace('"','')
        print '<br />'+line
        line=sec.next()
        line=line.rstrip()
      print '</td></tr>'
print '</table>'
