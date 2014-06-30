import os
from os import path
import urllib
from urllib import urlretrieve
from urllib2 import urlopen, HTTPError

from release.platforms import ftp_platform_map, buildbot2ftp
from release.l10n import makeReleaseRepackUrls
from release.paths import makeCandidatesDir
from util.paths import windows2msys, msys2windows
from util.file import directoryContains
from util.commands import run_cmd

import logging
log = logging.getLogger(__name__)

installer_ext_map = {
    'win32': ".exe",
    'win64': ".exe",
    'macosx': ".dmg",
    'macosx64': ".dmg",
    'linux': ".tar.bz2",
    'linux64': ".tar.bz2",
}


def getInstallerExt(platform):
    """ Return the file extension of the installer file on a given platform,
    raising a KeyError if the platform is not found """
    return installer_ext_map[platform]


def downloadReleaseBuilds(stageServer, productName, brandName, version,
                          buildNumber, platform, candidatesDir=None,
                          signed=False, usePymake=False):
    if candidatesDir is None:
        candidatesDir = makeCandidatesDir(productName, version, buildNumber,
                                          protocol='http', server=stageServer)
    files = makeReleaseRepackUrls(productName, brandName, version, platform,
                                  signed=signed)

    env = {}
    for fileName, remoteFile in files.iteritems():
        url = '/'.join([p.strip('/') for p in [candidatesDir,
                                               urllib.quote(remoteFile)]])
        log.info("Downloading %s to %s", url, fileName)
        urlretrieve(url, fileName)
        if fileName.endswith('exe'):
            if usePymake:
                env['WIN32_INSTALLER_IN'] = msys2windows(path.join(os.getcwd(),
                                                         fileName))
            else:
                env['WIN32_INSTALLER_IN'] = windows2msys(path.join(os.getcwd(),
                                                         fileName))
        else:
            if platform.startswith('win') and not usePymake:
                env['ZIP_IN'] = windows2msys(path.join(os.getcwd(), fileName))
            else:
                env['ZIP_IN'] = msys2windows(path.join(os.getcwd(), fileName))

    return env


def downloadUpdate(stageServer, productName, version, buildNumber,
                   platform, locale, candidatesDir=None):
    if candidatesDir is None:
        candidatesDir = makeCandidatesDir(productName, version, buildNumber,
                                          protocol='http', server=stageServer)
    fileName = '%s-%s.complete.mar' % (productName, version)
    destFileName = '%s-%s.%s.complete.mar' % (productName, version, locale)
    platformDir = buildbot2ftp(platform)
    url = '/'.join([p.strip('/') for p in [
        candidatesDir, 'update', platformDir, locale, fileName]])
    log.info("Downloading %s to %s", url, destFileName)
    remote_f = urlopen(url)
    local_f = open(destFileName, "wb")
    local_f.write(remote_f.read())
    local_f.close()
    return destFileName


def downloadUpdateIgnore404(*args, **kwargs):
    try:
        return downloadUpdate(*args, **kwargs)
    except HTTPError, e:
        if e.code == 404:
            # New locale
            log.warning('Got 404. Skipping %s' % e.geturl())
            return None
        else:
            raise


def rsyncFilesByPattern(server, userName, sshKey, source_dir, target_dir,
                        pattern):
    cmd = ['rsync', '-e',
           'ssh -l %s -oIdentityFile=%s' % (userName, sshKey),
           '-av', '--include=%s' % pattern, '--include=*/', '--exclude=*',
           '%s:%s' % (server, source_dir), target_dir]
    run_cmd(cmd)


def rsyncFiles(files, server, userName, sshKey, target_dir):
    cmd = ['rsync', '-e',
           'ssh -l %s -oIdentityFile=%s' % (userName, sshKey),
           '-av'] + files + ['%s:%s' % (server, target_dir)]
    run_cmd(cmd)
