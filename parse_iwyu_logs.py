#!/bin/env python
import sys , json
fd=open(sys.argv[1],'r')
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
print '<a href='+'"'+ sys.argv[1].split('/')[-1] + '"' + '>' + Access BuildLog + '</a><br/>'
print '<table  align="center">'
for l in fd:
  if 'remove' in l:
    sec=iter(fd)
    line=sec.next()
    if line.startswith('-'):
      print '<tr><td bgcolor="#00FFFF"><h2>'+l[70:].replace('lines','includes')+'</h2>'
      while line.startswith('-'):
        line=line.replace('<','')
        line=line.replace('>','')
        line=line.replace('"','')
        line=line.replace('- #include ','')
        print '<br/>'+line.split('//')[0]
        line=sec.next()
      print '</td></tr>'
      
  elif 'should add' in l:
    sec=iter(fd)
    line=sec.next()
    if line.startswith('#'):
      print '<tr><td bgcolor="#00FF90"><h2>'+l[70:].replace('lines','includes')+'</h2>'
      while line.startswith('#'):
        line=line.replace('<','')
        line=line.replace('>','')
        line=line.replace('#include ','').replace('"','')
        print '<br />'+line.split('//')[0]
        line=sec.next()
      print '</td></tr>'
print '</table>'
