#!/usr/bin/env python3
import gzip
import re
from json import dump
from os import environ
from os.path import exists, join

from _py2with3compatibility import run_cmd


def hasInclude(inc, src, cache):
    if src not in cache:
        cache[src] = {}
        for e in ['CMSSW_BASE', 'CMSSW_RELEASE_BASE', 'CMSSW_FULL_RELEASE_BASE']:
            if (e not in environ) or (not environ[e]):
                continue
            src_file = join(environ[e], 'src', src)
            if not exists(src_file):
                continue
            exp = re.compile(r'^\s*#\s*include\s*([<"])([^<"]+)([<"])\s*$')
            with open(src_file) as ref:
                lnum = 0
                for line in ref.readlines():
                    lnum += 1
                    m = exp.match(line)
                    if m:
                        cache[src][m.group(2)] = lnum
            break
    return inc in cache[src]


def readDeps(cache, depFile):
    with gzip.open(depFile, 'rt') as ref:
        for line in ref.readlines():
            data = line.strip().split(' ', 1)
            if len(data) < 2:
                continue
            cache[data[0]] = data[1].strip()
    return


def main():
    includes = {}
    uses = {}
    usedby = {}
    readDeps(uses, join(environ['CMSSW_RELEASE_BASE'], 'etc', 'dependencies', 'uses.out.gz'))
    readDeps(usedby, join(environ['CMSSW_RELEASE_BASE'], 'etc', 'dependencies', 'usedby.out.gz'))

    errs = {}
    checked = {}
    for inc in usedby:
        items = inc.split('/')
        if items[2] == 'interface':
            continue
        for src in usedby[inc].split(' '):
            sitems = src.split('/')
            if (items[0] == sitems[0]) and (items[1] == sitems[1]) and (items[2] == sitems[2]):
                continue
            if hasInclude(inc, src, includes):
                if src not in errs:
                    errs[src] = {}
                errs[src][inc] = includes[src][inc]
            if src in uses:
                for isrc in uses[src].strip().split(' '):
                    xchk = '%s:%s' % (src, inc)
                    if xchk in checked:
                        continue
                    checked[xchk] = 1
                    if not hasInclude(inc, isrc, includes):
                        continue
                    if isrc not in errs:
                        errs[isrc] = {}
                    errs[isrc][inc] = includes[isrc][inc]

    # Free memory
    del checked
    del includes
    del uses
    del usedby

    pkg_errs = {}
    for e in errs:
        pkg = '/'.join(e.split('/')[:2])
        if pkg not in pkg_errs:
            pkg_errs[pkg] = {}
        pkg_errs[pkg][e] = errs[e]

    outdir = 'invalid-includes'
    run_cmd('rm -f %s; mkdir %s' % (outdir, outdir))
    all_count = {}
    for p in sorted(pkg_errs):
        all_count[p] = len(pkg_errs[p])
        pdir = join(outdir, p)
        run_cmd('mkdir -p %s' % pdir)
        with open(join(pdir, 'index.html'), 'w') as ref:
            ref.write("<html><head></head><body>\n")
            for e in sorted(pkg_errs[p]):
                ref.write("<h3>%s:</h3>\n" % e)
                for inc in sorted(errs[e].keys()):
                    url = 'https://github.com/cms-sw/cmssw/blob/%s/%s#L%s' % (environ['CMSSW_VERSION'], e, errs[e][inc])
                    ref.write('<l1><a href="%s">%s</a></l1></br>\n' % (url, inc))
                ref.write("</ul></br>\n")
            ref.write("</body></html>\n")

    dump(all_count, open(outdir + '/summary.json', 'w'), indent=2, sort_keys=True, separators=(',', ': '))
