#!/usr/bin/env python
from __future__ import print_function
print("<html>")
print('<head>')
print('<meta charset="utf-8">')
print('<meta name="viewport" content="width=device-width, initial-scale=1">')
print('<link rel="stylesheet" href="https://maxcdn.bootstrapcdn.com/bootstrap/3.3.5/css/bootstrap.min.css">')
print('</head>')
print('<body>')
print('   <div class="container-fluid">')
print('    <div class="row-fluid">')
print('      <div style="text-align: center; class="span9">')
print('        <br /><h1 id="Welcome-to-jenkins-reports"><b> CMS Jenkins Projects </b></h1>')
print('        <p>This page displays a summary of all CMS Jenkins projects , their sub projects , upstream projects <br /> and downstream   	projects. To see the deatil and confgiuration of a project in Jenkins , click on project name. </p><br />')
print('      </div>')
print('    </div>')
print('  </div>')

from collections import defaultdict
parents = defaultdict(list)
import json
import time


try:
  fd = open('/tmp/report_gen.txt')
  txt = fd.read()
except Exception as e:
  print("Error reading the file")
data_uns = json.loads(txt)
data = sorted(list(data_uns.items()),key=lambda s: s[0].lower())

for item in data:
  name = item[1]['job_name']
  if name.startswith('DMWM'):
    continue
  print('<div class="container">')
  print('<ul class="nav nav-pills nav-stacked">')
  print("<li class="+'"'+"active"+'" '+ "id="+'"'+ name + '"'+ '><a href="https://cmssdt.cern.ch/jenkins/job/'+name+'"'+'><b>' + name.upper() +"</b></a></li>"+"<br />")
  print("<p>" , item[1]['job_desc'] , "</p><br />")
  if len(item[1]['downstream']) > 0:
    d = [ x.encode('utf-8') for x in item[1]['downstream'] ]
    for chd in d:
      parents[chd].append(name)
    print('<li>')  
    print("<b>DownStream Projects:</b> ", '  '.join([ '<a href='+'"#'+ x +'"'+ '>' + x + '</a>' for x in d ]) , "<br />")
    print('</li>')
  if len(item[1]['subprojects']) > 0:
    sub = [ x.encode('utf-8') for x in item[1]['subprojects'] ]
    print('<li>') 
    print("<b>Sub Projects:</b> ", ' '.join([ '<a href='+'"#'+ x +'"'+ '>' + x + '</a>' for x in sub  ]) , "<br />")
    print('</li>')
    for child in sub:
      parents[child].append(name)
  
  if len(item[1]['triggers_from']) > 0:
    trg = [ x.encode('utf-8') for x in item[1]['triggers_from']]
    item[1]['upstream'].extend(trg)
  for ent in parents:
    if ent == name:
        item[1]['upstream'].extend(parents[name])

  if len(item[1]['upstream']) > 0:
    item[1]['upstream'] = set(item[1]['upstream'])
    up = [ x.encode('utf-8') for x in item[1]['upstream']]
    print('<li>') 
    print("<b>UpStream Projects:</b> ", ' '.join([ '<a href='+'"#'+ x +'"'+ '>' + x + '</a>' for x in up  ]) , "<br />")
    print('</li><br />')
  print(' </ul>')
  print('</div>')

print('  <div class="container-fluid">')
print('    <div class="row-fluid">')
print('      <div class="span4"></div>')
print('      <div style="text-align: center; padding-top: 50px;" class="span4"><a style="font-size: 80%;" href="http://copyright.web.cern.ch">Copyright 1954-2015 CERN <br />'+ "Last Updated: "+ time.strftime("%Y-%m-%d %H:%M") + '</a></div>')
print('      <div class="span4"></div>')
print('    </div>')
print('  </div>')
print('</body>')
print('</html>')


