#!/usr/bin/env python
from __future__ import print_function
from sys import exit, argv
from os import pipe, close, fork, fdopen, write, waitpid
from os.path import exists
from time import sleep, time
from threading import Thread
from re import match
from array import array

from os.path import dirname, abspath
import sys
sys.path.append(dirname(dirname(dirname(abspath(__file__)))))  # in order to import cms-bot level modules
from _py2with3compatibility import run_cmd

def do_load(obj):
  mem_size = obj.memory*1024*1024
  cache = array('B', [0]) * mem_size
  print("Run: ", obj.id)
  while obj.state:
    x=0
    for j in range(1024):
      for k in range(1024):
          x=j*k
    sleep(0.001)

class LoadMaster (object):
  def __init__ (self, memory, max_child, pipe_in, max_time=0):
    self.memory = memory
    self.input = pipe_in
    self.max_child = max_child
    self.max_time = max_time
    self.childs = []

  def get_command(self):
    if self.input: return self.input.readline().strip()
    cFile = 'auto-load'
    while not exists(cFile): sleep(0.2)
    sleep(0.5)
    o, cmd = run_cmd("head -1 %s; rm -f %s" % (cFile, cFile))
    return cmd.strip()

  def remove_child(self):
    if len(self.childs)==0: return
    write(self.childs[-1][1], 'stop\n')
    waitpid(self.childs[-1][0], 0)
    self.childs.pop()
    print("Childs:",len(self.childs))

  def remove_childs(self, count):
    for c in range(count): self.remove_child()

  def remove_all(self):
    self.remove_childs(self.max_child)

  def add_child(self):
    if self.max_child==len(self.childs): return
    pin, pout = pipe()
    pid = fork()
    if pid == 0:
      close(pout)
      c = LoadClient(len(self.childs), self.memory)
      c.start(pin)
      exit(0)
    else:
      close(pin)
      self.childs.append([pid, pout])
      print("Childs:",len(self.childs))

  def add_childs(self, count):
    for c in range(count): self.add_child()

  def add_all(self):
    self.add_childs(self.max_child)

  def start(self):
    stime = time()
    while True:
      if self.max_time<=0:
        cmd = self.get_command()
      elif (time()-stime)>self.max_time:
        cmd = "exit"
      elif self.childs:
        sleep(1)
        continue
      else:
        cmd = "start"
      print("master: %s" % cmd)
      if cmd in ['stop', 'exit']: self.remove_all()
      elif cmd=='start': self.add_all()
      else:
        m = match('^([+]|[-]|)([1-9][0-9]{0,1})$', cmd)
        if m:
          count = int(m.group(2))
          if m.group(1)=='+': self.add_childs(count)
          elif m.group(1)=='-': self.remove_childs(count)
          else:
            while len(self.childs)>count: self.remove_child()
            while len(self.childs)<count: self.add_child()
      if cmd=='exit': break
    return

class LoadClient (object):
  def __init__ (self, cid, memory):
    self.memory = memory
    self.id    = cid
    self.state = True

  def start(self, pipe_in):
    thr = Thread(target=do_load, args=(self, ))
    thr.start()
    pin = fdopen(pipe_in)
    while self.state:
      cmd = pin.readline().strip()
      print("%s: %s" % (self.id, cmd))
      if cmd=='stop': self.state = False
    pin.close()
    thr.join()
    print("Done:",self.id)
    exit(0)

childs=int(argv[1])
memory=int(argv[2])
try: max_time=int(argv[3])
except: max_time=0
master = LoadMaster(memory, childs, None, max_time)
master.start()
print("ALL OK")

