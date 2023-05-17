#! /usr/bin/python3

# missing: bin/computeprof
# missing: version.json
# could be update: lib64/pkconfig/*.pc

import argparse
import glob
import hashlib
import json
import os
import re
import shutil
import stat
import subprocess
import sys
import tarfile
import tempfile
import urllib.request

# Global verbosity levels
ERROR = 0
WARNING = 1
INFO = 2
DEBUG = 3

verbose = INFO

def error(text):
    if verbose >= ERROR:
        print("Error:", text)

def warning(text):
    if verbose >= WARNING:
        print("Warning:", text)

def info(text):
    if verbose >= INFO:
        print("Info:", text)

def debug(text):
    if verbose >= DEBUG:
        print("Debug:", text)


# Describe an NVIDIA software component for a specific architecture
class Component:
    def __init__(self, catalog = None, key = None, os_arch = None):
        # General information about an NVIDIA software component
        # key used in the JSON catalog, e.g. 'cuda_cccl'
        self.key = str()
        # name of the software component, e.g. 'CXX Core Compute Libraries'
        self.name = str()
        # version of the individual component, e.g. '12.0.90'
        self.version = str()
        # license of the individual component: 'NVIDIA Driver', 'NVIDIA SLA', 'CUDA Toolkit'
        self.license = str()
        # Information about the package for a given architecture
        # package path, relative to the dorectory that contains the JSON catalog
        self.path = str()
        # package size
        self.size = int()
        # package hashes
        self.md5sum = str()
        self.sha256 = str()

        # initialise the component from the catalog
        if catalog is not None:
            self.fill(catalog, key, os_arch)

    def fill(self, catalog, key, os_arch):
        # Check for None arguments
        if catalog is None:
            raise TypeError('catalog cannot be None')
        if key is None:
            raise TypeError('key cannot be None')
        if os_arch is None:
            raise TypeError('os_arch cannot be None')

        # Store the key
        self.key = key

        # Extract the general information about the NVIDIA software component
        if key not in catalog:
            raise RuntimeError(f"the component '{key}' is not available in the JSON catalog")
        component = catalog[key]
        self.name    = component['name']
        self.version = component['version']
        self.license = component['license']

        # Extract the architecture-specific information about the package
        if os_arch not in component:
            raise RuntimeError(f"the '{name}' component is not available for the '{os_arch}' architecture")
        package = component[os_arch]
        self.path   = package['relative_path']
        self.size   = int(package['size'])
        self.md5sum = package['md5']
        self.sha256 = package['sha256']



# Remove all the suffixes in the list
def removesuffix(arg, *suffixes):
    modified = True
    while modified:
        modified = False
        for suffix in suffixes:
            if arg.endswith(suffix):
                arg = arg[:-len(suffix)]
                modified = True
                break

    return arg

# Move the file or directory tree "src" to "dst", merging any directories that already exist.
# Similar to shutil.copytree(src, dst, symlinks=True, ignore=None, copy_function=shutil.move, ignore_dangling_symlinks=True, dirs_exist_ok=True)
def movetree(src, dst, overwrite=False):
    # Make sure the parent of the dst tree exists
    dstparent = os.path.normpath(os.path.join(dst, '..'))
    os.makedirs(dstparent, exist_ok=True)

    # If the dst tree does not exist, simply move the src tree there
    if not os.path.exists(dst):
        shutil.move(src, dst)
        return

    # If the dst tree exists the bahaviour depends on the src and dst types.
    srcmode = os.lstat(src).st_mode
    dstmode = os.lstat(dst).st_mode

    # If both src and dst are files or links, the behaviour depends on the `overwrite` parameter.
    if (stat.S_ISLNK(srcmode) or stat.S_ISREG(srcmode)) and (stat.S_ISLNK(dstmode) or stat.S_ISREG(dstmode)):
        # If overwrite is True, overwrite dst.
        if (overwrite):
            os.remove(dst)
            shutil.move(src, dst)
        # If overwrite is False, ignore dst and leave src at its original location.
        else:
            pass

    # If both src and dst are directories, merge src into dts
    elif stat.S_ISDIR(srcmode) and stat.S_ISDIR(dstmode):
        # Move all the contents of the src tree into dst.
        for entry in os.scandir(src):
            srcname = os.path.join(src, entry.name)
            dstname = os.path.join(dst, entry.name)
            movetree(srcname, dstname, overwrite)
        # Remove src if it is now empty
        if not any(os.scandir(src)):
            os.rmdir(src)

    # Other combinations are not supported: directories cannot be merged with files or links, etc.
    else:
        raise RuntimeError(f"Cannot merge or overwrite entries of different types: {src} vs {dst}")


# Download a JSON catalog from any URL supported by urllib ('http://...', 'https://...', 'file:...', etc.)
# and deserialise it into a python dictionary.
def download_catalog(url, download_dir):
    # Open the JSON catalog URL
    try:
        request = urllib.request.urlopen(url)
    except Exception as e:
        error(f"error while opening the JSON catalog at {url}")
        raise e

    # Check the content type
    try:
        content_type = request.headers['Content-type']
        if (content_type != 'application/json'):
            warning(f"the JSON catalog at {url} has the content type '{content_type}' instead of 'application/json'")
    except:
        warning(f"the JSON catalog at {url} does not have a valid content type")

    # Downlod the JSON catalog
    json_file = os.path.join(download_dir, os.path.basename(url))
    urllib.request.urlretrieve(url, json_file)

    return json_file


# Parse a catalog and return the list of components available for the given architecture.
def parse_catalog(json_file, os_arch):
    # Load and deserialise the JSON catalog
    try:
        catalog = json.load(open(json_file, 'r'))
    except json.decoder.JSONDecodeError as e:
        error(f"the catalog at is not a valid JSON file")
        raise e

    # Skip the 'release_date' and other non-package entries, and the components
    # that are not available for the given architecture.
    components = [ Component(catalog, key, os_arch) for key in catalog if type(catalog[key]) is dict and os_arch in catalog[key] ]
    return components


# Check the size, checksum and hash of locally downloaded software component package.
def check_package(component, local_file):
    name = os.path.basename(component.path)

    # Check the file size reported by the filesystem
    stats = os.stat(local_file)
    if (stats.st_size != component.size):
        raise RuntimeError(f"package '{name}' should have a size of {component.size} bytes, but file {local_file} has a size of {stats.st_size} bytes.")

    # Read the file in buffered mode, compute its size, the md5 checksum and sha256 hash one chunk at a time
    size = 0
    algo_md5sum = hashlib.md5()
    algo_sha256 = hashlib.sha256()
    with open(local_file, 'rb') as f:
        chunk = f.read(stats.st_blksize)
        while chunk:
            size += len(chunk)
            algo_md5sum.update(chunk)
            algo_sha256.update(chunk)
            chunk = f.read(stats.st_blksize)

    # Check the file size, checksum and hash with the expected values
    if (size != component.size):
        raise RuntimeError(f"package '{name}' should have a size of {component.size} bytes, but only {size} bytes could be read from file {local_file}.")
    md5sum = algo_md5sum.hexdigest()
    if (md5sum != component.md5sum):
        raise RuntimeError(f"package '{name}' should have an md5 checksum of {component.md5sum}, but file {local_file} has an md5 checksum of {md5sum}.")
    sha256 = algo_sha256.hexdigest()
    if (sha256 != component.sha256):
        raise RuntimeError(f"package '{name}' should have a sha256 hash of {component.sha256}, but file {local_file} has a sha256 hash of {sha256}.")


# Download a software component package relative to `base_url` and save it to a local file under `download_dir`.
def download_package(base_url, download_dir, component):
    url = os.path.join(base_url, component.path)
    target = os.path.join(download_dir, os.path.basename(component.path))

    # If the target file already exists, check it size, checksum and hash.
    if os.path.isfile(target):
        try:
            check_package(component, target)
            info(f"file {target} exists and matches the expected size, checksum and hash.")
            return target
        except RuntimeError as e:
            # If the checks fail, delete the local file and try to download it again.
            warning(f"file {target} exists, but does not match the expected size, checksum or hash:")
            print(e)
            os.remove(target)

    # Downlod the package and check its size, checksum and hash
    info(f"downloading {url} to local file {target}.")
    urllib.request.urlretrieve(url, target)
    check_package(component, target)
    return target


# Unpack a package under the given directory
def unpack_package(package, local_dir):
    # Open the package as a tar archive
    try:
        archive = tarfile.open(package, 'r:*')
    except:
        raise RuntimeError(f"the package {package} is not a valid archive.")

    # Check that all components of the archive expand inside the expected directory
    package_name = os.path.basename(package)
    package_name = removesuffix(package_name, '.tar', '.tgz', '.gz', '.bz2', '.xz')
    archive_dir = os.path.join(local_dir, package_name)
    for info in archive:
        if not os.path.normpath(os.path.join(local_dir, info.name)).startswith(archive_dir):
            raise RuntimeError(f"the package {package} contents are not in the expected directory.")

    # Delete any pre-existing directory (or file) with the same name
    if os.path.exists(archive_dir):
        info(f"will delete existing directory {archive_dir}")
        shutil.rmtree(archive_dir)

    # Unpack the archive
    archive.extractall(local_dir)
    archive.close()

    # Return the directory where the archive has been extracted
    return archive_dir


class RemapRules:
    def __init__(self, move = [], keep = [], link = [], skip = [], replace = []):
        self.move = list(move)
        self.keep = list(keep)
        self.link = list(link)
        self.skip = list(skip)
        self.replace = list(replace)

    def apply(self, archive_dir, install_dir):
        # move files or directory from 'src' to 'dst'
        for (src, dst) in self.move:
            if src == '.':
                src = archive_dir
            else:
                src = os.path.join(archive_dir, src)
            dst = os.path.join(install_dir, dst)
            if os.path.exists(src):
                movetree(src, dst)
        # keep files or directory at 'arg'
        for arg in self.keep:
            if arg == '.':
                src = archive_dir
                dst = install_dir
            else:
                src = os.path.join(archive_dir, arg)
                dst = os.path.join(install_dir, arg)
            if os.path.exists(src):
                movetree(src, dst)
        # symlink files or directory from 'src' (relative) to 'dst'
        for (src, dst) in self.link:
            dst = os.path.join(install_dir, dst)
            tmp = os.path.join(os.path.dirname(dst), src)
            debug(f"attempt to symlink {src} to {dst}")
            if not os.path.exists(tmp):
                debug(f"{tmp} does not exist")
                continue
            if os.path.lexists(dst):
                debug(f"{dst} already exists")
                continue
            debug(f"will symlink {src} to {dst}")
            os.symlink(src, dst)
        # delete files or directories at 'src'
        for src in self.skip:
            src = os.path.join(archive_dir, src)
            for src in glob.glob(src):
                debug(f"will skip and delete {src}")
                if os.path.isdir(src) and not os.path.islink(src):
                    shutil.rmtree(src)
                else:
                    os.remove(src)
        # apply pair of pattern, text replacements in 'reps' to 'src'
        for src,reps in self.replace:
            src = os.path.join(archive_dir, src)
            debug(f"applying replacements to {src}")
            if not os.path.exists(src):
                warning(f"{src} does not exist")
                continue
            mode = stat.S_IMODE(os.stat(src).st_mode)
            with open(src, 'r') as f:
                content = f.read()
            for pattern, replace in reps:
                content = content.replace(pattern, replace)
            os.chmod(src, mode | stat.S_IWUSR)
            with open(src, 'w') as f:
                f.write(content)
            os.chmod(src, mode)


def build_remap_rules(target):

    remap = {
        # these rules are applied to every package, if the sources exist, after the package-specific ones
        '*': RemapRules(
            move = [
                # the source is relative to the unpacked package directory
                # the destination is relative to the installation directory
                ('lib',        f'{target}/lib'),
                ('include',    f'{target}/include'),
                ('pkg-config', f'{target}/lib/pkgconfig'),
                ('res',        f'{target}/res'),
            ],
            keep = [
                # relative to the unpacked package directory, move to the
                # same location relative to the installation directory
            ],
            link = [
                # both source and destination are relative to the installation directory
                # and will use relative symlinks
                (f'{target}/lib',     'lib64'),
                (f'{target}/include', 'include'),
                (f'{target}/res',     'res'),
            ],
            skip = [
                # relative to the unpacked package directory, allows wildcards
            ],
            replace = [
                # list of files, patterns and replacement text
            ]
        ),
        'cuda_cupti': RemapRules(
            move = [
                ('samples', 'extras/CUPTI/samples'),
                ('doc',     'extras/CUPTI/doc'),
            ]
        ),
        'cuda_demo_suite' : RemapRules(
            move = [
                ('demo_suite', 'extras/demo_suite'),
            ]
        ),
        'cuda_documentation': RemapRules(
            keep = [
                '.'
            ]
        ),
        'cuda_gdb': RemapRules(
            skip = [
                'extras/cuda-gdb-*.src.tar.gz',
            ]
        ),
        'cuda_nvvp' : RemapRules(
            link = [
                ('nvvp', 'bin/computeprof')
            ]
        ),
        'libcufile' : RemapRules(
            move = [
                ('README',          'gds/README'),
                ('etc/cufile.json', 'gds/cufile.json'),
                ('samples',         'gds/samples'),
                ('tools',           'gds/tools'),
            ],
            skip = [
                'etc',
            ]
        ),
        'nvidia_driver': RemapRules(
            move = [
                ('.', 'drivers')
            ]
        ),
        'libnvidia_nscq': RemapRules(
            move = [
                ('.', 'drivers')
            ]
        ),
        'nvidia_fs' : RemapRules(
            move = [
                ('.', 'drivers/nvidia_fs')
            ]
        ),
        'fabricmanager' : RemapRules(
            move = [
                ('.', 'fabricmanager')
            ]
        ),
    }

    return remap



# Move the contents of package to the installation directory
def install_package(component, archive_dir, install_dir, rules):
        # Apply the package-specific remap rules
        if component.key in rules:
            rules[component.key].apply(archive_dir, install_dir)

        # If the top-level archive directory was moved by a remap rule, there is nothing left to do
        if not os.path.isdir(archive_dir):
            return

        # Apply the global remap rules
        if '*' in rules:
            rules['*'].apply(archive_dir, install_dir)

        # Move any files in the top-level archive directory to a .../share/doc/package subdirectory of the installation directory
        top_level_files = [f'{archive_dir}/{f.name}' for f in os.scandir(archive_dir) if not f.is_dir(follow_symlinks=False)]
        if (top_level_files):
            share_doc = os.path.join(install_dir, 'share/doc', component.key)
            os.makedirs(share_doc)
            for f in top_level_files:
                shutil.move(f, share_doc)

        # Move everything else to the installation directory
        movetree(archive_dir, install_dir)


def main():
    global verbose

    # Base URL for the NVIDIA JSON catalogs and the redistributable software components
    base_url = 'https://developer.download.nvidia.com/compute/cuda/redist/'

    # Packages that should _not_ be unpacked and installed
    blacklist = [ 'fabricmanager', 'libnvidia_nscq' ]

    # If not empty, restrinct the installation to the packages in this list, minus those in the blacklist.
    whitelist = [ ]

    # Command line arguments and options
    parser = argparse.ArgumentParser(
        description = 'Download, unpack and install the CUDA runtime.')

    parser.add_argument('version', metavar='VERSION', nargs='*', help='Version to download, unpack and install, e.g. 11.7.1 or 12.0.0')

    # Possible architectures for the NVIDIA redistributables: 'x86_64', 'ppc64le', 'sbsa' (aarch64 server), 'aarch64' (aarch64 embedded)
    # We supporty only aarch server, so we use 'aarch64' to select 'sbsa'
    parser.add_argument('-a', '--arch', metavar='ARCH', choices=['x86_64', 'aarch64', 'ppc64le'], default='x86_64', 
        help='the architecture to download the components for; aarch64 selects the ARM sbsa architecture (Server Base System Architecture)')
    # We support only Linux, so we actually override any user's choice with 'linux'
    parser.add_argument('-o', '--os', metavar='OS', choices=['rhel7', 'rhel8', 'rhel9'], default='rhel9', 
        help='the operating system to download the components for; currently this is ignored, because a single set of components supports all recent Linux versions')
    parser.add_argument('-d', '--download-dir', metavar='PATH', default=None,
        help='directory where the components should be downloaded; the default is /cvmfs/patatrack.cern.ch/externals/ARCH/OS/nvidia/download/cuda-VERSION')
    parser.add_argument('-i', '--install-dir', metavar='PATH', default=None,
        help='directory where the components should be installed; the default is /cvmfs/patatrack.cern.ch/externals/ARCH/OS/nvidia/cuda-VERSION')
    parser.add_argument('-u', '--base-url', metavar='URL', default=base_url, 
        help='base URL for the NVIDIA JSON catalogs and the redistributable software components')
    parser.add_argument('-t', '--temp-dir', metavar='PATH', default=None, 
        help='temporary directory for unpacking the components; if not specified a system default will be used')
    parser.add_argument('-x', '--exclude', metavar='COMPONENT', nargs='*', default=[],
        help='components to exclude from the installation; the default is%s' % (': ' + ' '.join(blacklist) if blacklist else ' to install all components'))
    parser.add_argument('-s', '--select', metavar='COMPONENT', nargs='*', default=[],
        help='components to include in the installation; the default is%s' % (': ' + ' '.join(whitelist) if whitelist else ' to install all components'))
    parser.add_argument('-c', '--cvmfs', action='store_true', default=False,
        help='special handling for CVMFS targets: cvmfs_server transaction/publish patatrack.cern.ch, create .cvmfscatalog in the download and installation directories')
    parser.add_argument('-v', '--verbose', action='store_true', default=False,
        help='be more verbose')

    args = parser.parse_args()
    if args.verbose:
        verbose = DEBUG

    # We supporty only aarch server, so we use 'aarch64' to select 'sbsa'
    if args.arch == 'aarch64':
        args.arch = 'sbsa'

    # Valid combinations: 'linux-x86_64', 'linux-ppc64le', 'linux-sbsa', 'windows-x86_64', 'linux-aarch64'
    os_arch = f'linux-{args.arch}'

    # Customise the remap rules for the ARCH-OS target
    target = f'targets/{args.arch}-linux'
    rules = build_remap_rules(target)

    # Pattern used to check the version numbers (e.g. 11.7.1 or 12.0.0)
    version_check = re.compile(r'^[1-9][0-9]*\.[0-9]+\.[0-9]+$')

    # Blacklist and whitelist
    if args.exclude:
        blacklist = args.exclude
    if args.select:
        whitelist = args.select

    for arg in args.version:

        # Start a CVMFS transaction
        if args.cvmfs:
            subprocess.run(['/bin/cvmfs_server', 'transaction', 'patatrack.cern.ch'])

        # CUDA version and catalog URL
        if 'https://' in arg:
            version = os.path.basename(arg).replace('redistrib_', '').replace('.json', '')
            url = arg
            base = os.path.dirname(arg)
        else:
            version = arg
            url = f'https://developer.download.nvidia.com/compute/cuda/redist/redistrib_{version}.json'
            base = args.base_url
        if not base.endswith('/'):
            base += '/'

        # Check the version number
        if not version_check.match(version):
            raise RuntimeError(f'Error: invalid CUDA version {version}')

        # Download directory
        if args.download_dir is None:
            download_dir = f'/cvmfs/patatrack.cern.ch/externals/{args.arch}/{args.os}/nvidia/download/cuda-{version}'
        else:
            download_dir = args.download_dir
        os.makedirs(download_dir, exist_ok=True)

        # Temporary directory for unpacking downloaded archive files, or None for a default location
        if args.temp_dir is None:
            temp_dir = tempfile.mkdtemp()
        else:
            temp_dir = args.temp_dir
            os.makedirs(temp_dir)

        # Installation directory
        if args.install_dir is None:
            install_dir = f'/cvmfs/patatrack.cern.ch/externals/{args.arch}/{args.os}/nvidia/cuda-{version}'
        else:
            install_dir = args.install_dir

        # Create a CVMFS catalog in the download directory
        if args.cvmfs:
            open(f'{download_dir}/.cvmfscatalog', 'w').close()

        info(f"downloading CUDA {version} catalog from {url}")
        catalog = download_catalog(url, download_dir)
        components = parse_catalog(catalog, os_arch)

        # Version-dependent rules for Nsight Compute and Nsight Systems
        cuda_major, cuda_minor, cuda_point = version.split('.')
        for component in components:
            # Nsight Compute
            if component.key == 'nsight_compute':
                tool_version = '.'.join(component.version.split('.')[0:3])
                rules['nsight_compute'] = RemapRules(
                    move = [
                        # move source to destination in the installation directory
                        (f'nsight-compute/{tool_version}', f'nsight-compute-{tool_version}'),
                    ],
                    skip = [
                        # skip sources
                        'nsight-compute',
                    ],
                )
            # Nsight Systems
            if component.key == 'nsight_systems':
                tool_version = '.'.join(component.version.split('.')[0:3])
                rules['nsight_systems'] = RemapRules(
                    move = [
                        # move source to destination in the installation directory
                        ('bin/nsight-exporter', 'bin/nsys-exporter'),
                        (f'nsight-systems/{tool_version}', f'nsight-systems-{tool_version}'),
                    ],
                    skip = [
                        # skip sources
                        'nsight-systems',
                    ],
                    replace = [
                        # list of files, each associated to a list of patterns and replacement text
                        ('bin/nsys',    [('#VERSION_RSPLIT#', tool_version), ('#CUDA_MAJOR#', cuda_major), ('#CUDA_MINOR#', cuda_minor)]),
                        ('bin/nsys-ui', [('#VERSION_RSPLIT#', tool_version), ('#CUDA_MAJOR#', cuda_major), ('#CUDA_MINOR#', cuda_minor)]),
                    ]
                )

        # Populate a list of all packages to be installed
        packages = set(component.key for component in components)
        if whitelist:
            packages &= set(whitelist)
        if blacklist:
            packages -= set(blacklist)

        # Download, unpack and install the components
        for component in components:
            # Skip components that should not be installed
            if component.key not in packages:
                continue

            # Download the package to a temporary directory
            package = download_package(base, download_dir, component)

            # Unpack the package to a subdirectory of the temporary directory
            archive_dir = unpack_package(package, temp_dir)

            # Move the contents of the package to the installation directory
            install_package(component, archive_dir, install_dir, rules)

        # copy json file for future use
        cms_conf_dir = os.path.join(install_dir, ".cms")
        os.makedirs(cms_conf_dir)
        shutil.copy(catalog, cms_conf_dir)

        # Clean up the temporary directory
        shutil.rmtree(temp_dir)

        # Create a CVMFS catalog in the installation directory
        if args.cvmfs:
            open(f'{install_dir}/.cvmfscatalog', 'w').close()

        # Commit and publish the CVMFS transaction
        if args.cvmfs:
            subprocess.run(['/bin/cvmfs_server', 'publish', 'patatrack.cern.ch'])

if __name__ == "__main__":
    main()

