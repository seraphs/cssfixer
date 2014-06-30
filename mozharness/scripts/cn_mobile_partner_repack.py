#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****
"""mobile_partner_repack.py

"""

from copy import deepcopy
import os
import sys

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.errors import ZipErrorList
from mozharness.base.log import FATAL
from mozharness.base.transfer import TransferMixin
from mozharness.base.vcs.vcsbase import MercurialScript
from mozharness.mozilla.l10n.locales import LocalesMixin
from mozharness.mozilla.release import ReleaseMixin
from mozharness.mozilla.signing import MobileSigningMixin

SUPPORTED_PLATFORMS = ["android"]


# MobilePartnerRepack {{{1
class MobilePartnerRepack(LocalesMixin, ReleaseMixin, MobileSigningMixin,
                          TransferMixin, MercurialScript):
    config_options = [[
        ['--locale', ],
        {"action": "extend",
         "dest": "locales",
         "type": "string",
         "help": "Specify the locale(s) to repack"
         }
    ], [
        ['--partner', ],
        {"action": "extend",
         "dest": "partners",
         "type": "string",
         "help": "Specify the partner(s) to repack"
         }
    ], [
        ['--locales-file', ],
        {"action": "store",
         "dest": "locales_file",
         "type": "string",
         "help": "Specify a json file to determine which locales to repack"
         }
    ], [
        ['--tag-override', ],
        {"action": "store",
         "dest": "tag_override",
         "type": "string",
         "help": "Override the tags set for all repos"
         }
    ], [
        ['--platform', ],
        {"action": "extend",
         "dest": "platforms",
         "type": "choice",
         "choices": SUPPORTED_PLATFORMS,
         "help": "Specify the platform(s) to repack"
         }
    ], [
        ['--user-repo-override', ],
        {"action": "store",
         "dest": "user_repo_override",
         "type": "string",
         "help": "Override the user repo path for all repos"
         }
    ], [
        ['--release-config-file', ],
        {"action": "store",
         "dest": "release_config_file",
         "type": "string",
         "help": "Specify the release config file to use"
         }
    ], [
        ['--version', ],
        {"action": "store",
         "dest": "version",
         "type": "string",
         "help": "Specify the current version"
         }
    ], [
        ['--buildnum', ],
        {"action": "store",
         "dest": "buildnum",
         "type": "int",
         "default": 1,
         "metavar": "INT",
         "help": "Specify the current release build num (e.g. build1, build2)"
         }
    ]]

    def __init__(self, require_config_file=True):
        self.release_config = {}
        LocalesMixin.__init__(self)
        MercurialScript.__init__(
            self,
            config_options=self.config_options,
            all_actions=[
                "pull",
                "download",
                "repack",
                "sign",
                "upload-signed-bits",
                "summary",
            ],
            require_config_file=require_config_file
        )

    # Helper methods {{{2
    def add_failure(self, platform, locale, **kwargs):
        s = "%s:%s" % (platform, locale)
        if 'message' in kwargs:
            kwargs['message'] = kwargs['message'] % {'platform': platform, 'locale': locale}
        super(MobilePartnerRepack, self).add_failure(s, **kwargs)

    def query_failure(self, platform, locale):
        s = "%s:%s" % (platform, locale)
        return super(MobilePartnerRepack, self).query_failure(s)

    # Actions {{{2

    def pull(self):
        c = self.config
        repos = []
        replace_dict = {}
        if c.get("user_repo_override"):
            replace_dict['user_repo_override'] = c['user_repo_override']
            # deepcopy() needed because of self.config lock bug :(
            for repo_dict in deepcopy(c['repos']):
                repo_dict['repo'] = repo_dict['repo'] % replace_dict
                repos.append(repo_dict)
        else:
            repos = c['repos']
        self.vcs_checkout_repos(repos, parent_dir=c['work_dir'],
                                tag_override=c.get('tag_override'))

    def download(self):
        c = self.config
        rc = self.query_release_config()
        locales = self.query_locales()
        replace_dict = {
            'buildnum': rc['buildnum'],
            'version': rc['version'],
        }
        # Clear the work folder
        workdir = c['workdir']
        self.rmtree(workdir)
        self.mkdir_p(workdir)
        success_count = total_count = 0
        for platform in c['platforms']:
            base_installer_name = c['installer_base_names'][platform]
            base_url = os.path.join(c['download_base_url'], base_installer_name)
            replace_dict['platform'] = platform
            for locale in locales:
                replace_dict['locale'] = locale
                url = base_url % replace_dict
                installer_name = base_installer_name % replace_dict
                parent_dir = os.path.join(workdir, 'original/%s/%s' % (platform, locale))
                file_path = os.path.join(parent_dir, installer_name)
                self.mkdir_p(parent_dir)
                total_count += 1
                if self.copyfile(url, file_path):
                    self.add_failure(platform, locale,
                                     message="Unable to dowload %(platform)s:%(locale)s installer!")
                else:
                    success_count += 1
        self.summarize_success_count(success_count, total_count,
                                     message="Downloaded %d of %d installers successfully.")

    def _repack_apk(self, partner, orig_path, repack_path, version):
        """ Repack the apk with a partner update channel.
        Returns True for success, None for failure
        """
        zip_bin = self.query_exe("zip")
        unzip_bin = self.query_exe("unzip")
        file_name = os.path.basename(orig_path)
        tmp_dir = os.path.join(self.config['work_dir'], 'tmp')
        tmp_file = os.path.join(tmp_dir, file_name)
        tmp_prefs_dir = os.path.join(tmp_dir, 'defaults', 'pref')
        tmp_distribution = os.path.join(tmp_dir,'distribution')
        # Error checking for each step.
        # Ignoring the mkdir_p()s since the subsequent copyfile()s will
        # error out if unsuccessful.
        if self.rmtree(tmp_dir):
            return
        self.mkdir_p(tmp_prefs_dir)
        if self.copyfile(orig_path, tmp_file):
            return
        if self.copytree(self.config['distribution_dir'],tmp_distribution):
            return
        if self.write_to_file(os.path.join(tmp_distribution,'preferences.json'),
 '''{
    "Global":{
    "id":"mozillaonline",
    "version":"%s",
    "about":"Mozilla Online"
    }
}''' % version)is None:
            return
        
        if self.run_command([zip_bin, '-0r', file_name, 'distribution'],
                            error_list=ZipErrorList,
                            return_type='num_errors',
                            cwd=tmp_dir):
            self.error("Can't add distribution to %s!" % file_name)
            return
        if self.write_to_file(os.path.join(tmp_prefs_dir, 'partner.js'),
                              'pref("extensions.cmmanager.channelid", "%s");' % partner
                              ) is None:
            return
        if self.run_command([unzip_bin, '-q', file_name, 'assets/omni.ja'],
                            error_list=ZipErrorList,
                            return_type='num_errors',
                            cwd=tmp_dir):
            self.error("Can't extract omni.ja from %s!" % file_name)
            return
        if self.run_command([zip_bin, '-0r', 'assets/omni.ja',
                             'defaults/pref/partner.js'],
                            error_list=ZipErrorList,
                            return_type='num_errors',
                            cwd=tmp_dir):
            self.error("Can't add partner.js to omni.ja!")
            return
        if self.run_command([zip_bin, '-0r', file_name, 'assets/omni.ja'],
                            error_list=ZipErrorList,
                            return_type='num_errors',
                            cwd=tmp_dir):
            self.error("Can't re-add omni.ja to %s!" % file_name)
            return
        if self.unsign_apk(tmp_file):
            return
        repack_dir = os.path.dirname(repack_path)
        self.mkdir_p(repack_dir)
        if self.copyfile(tmp_file, repack_path):
            return
        return True

    def repack(self):
        c = self.config
        rc = self.query_release_config()
        locales = self.query_locales()
        success_count = total_count = 0
        for platform in c['platforms']:
            for locale in locales:
                installer_name = c['installer_base_names'][platform] % {'version': rc['version'], 'locale': locale}
                if self.query_failure(platform, locale):
                    self.warning("%s:%s had previous issues; skipping!" % (platform, locale))
                    continue
                original_path = os.path.join(c['workdir'], 'original/%s/%s/%s' % (platform, locale, installer_name))
                for partner in c['partner_config'].keys():
                    repack_path = os.path.join(c['workdir'], 'unsigned/%s/%s/%s_%s' % (platform, locale, partner, installer_name))
                    total_count += 1
                    if self._repack_apk(partner, original_path, repack_path, rc['version']):
                        success_count += 1
                    else:
                        self.add_failure(platform, locale,
                                         message="Unable to repack %(platform)s:%(locale)s installer!")
        self.summarize_success_count(success_count, total_count,
                                     message="Repacked %d of %d installers successfully.")

    def _upload(self, dir_name=""):
        c = self.config
        rc = self.query_release_config()
        locales = self.query_locales()
        # Clear the output folder
        output_dir = c['output_dir']
        self.rmtree(output_dir)
        self.mkdir_p(output_dir)
        success_count = total_count = 0
        for platform in c['platforms']:
            for locale in locales:
                installer_name = c['installer_base_names'][platform] % {'version': rc['version'], 'locale': locale}
                for partner in c['partner_config'].keys():
                    filename = '%s_%s'% (partner, installer_name)
                    signed_path = os.path.join(c['workdir'], 'signed/%s/%s/%s' % (platform, locale, filename))
                    dest_path = os.path.join(output_dir, filename)
                    total_count += 1
                    if self.copyfile(signed_path, dest_path):
                        self.add_failure(platform, locale,
                                         message="Unable to copy %s!" % filename)
                        self.rmtree(signed_dir)
                    else:
                        success_count += 1
        self.summarize_success_count(success_count, total_count,
                                     message="Uploaded %d of %d apks successfully.")

    def sign(self):
        c = self.config
        rc = self.query_release_config()
        locales = self.query_locales()
        success_count = total_count = 0
        for platform in c['platforms']:
            for locale in locales:
                installer_name = c['installer_base_names'][platform] % {'version': rc['version'], 'locale': locale}
                if self.query_failure(platform, locale):
                    self.warning("%s:%s had previous issues; skipping!" % (platform, locale))
                    continue
                for partner in c['partner_config'].keys():
                    unsigned_path = os.path.join(c['workdir'], 'unsigned/%s/%s/%s_%s' % (platform, locale, partner, installer_name))
                    signed_dir = os.path.join(c['workdir'], 'signed/%s/%s/' % (platform, locale))
                    signed_path = os.path.join(signed_dir, '%s_%s' % (partner, installer_name))
                    total_count += 1
                    self.info("Signing %s %s." % (platform, locale))
                    if not os.path.exists(unsigned_path):
                        self.error("Missing apk %s!" % unsigned_path)
                        continue
                    if self.sign_apk(unsigned_path, c['keystore'],
                                     c['sign_password'], c['sign_password'],
                                     c['key_alias']) != 0:
                        self.add_summary("Unable to sign %s:%s apk!" % (platform, locale), level=FATAL)
                    else:
                        # verify signatures.
                        status = self.verify_android_signature(
                            unsigned_path,
                            script=c['signature_verification_script'],
                            tools_dir=c['tools_dir'],
                            key_alias=c['key_alias'],
                        )
                        if status:
                            self.add_failure(platform, locale, message="Errors verifying %s binary!" % unsigned_path)
                            # No need to rm because upload is per-locale
                            continue
                        self.mkdir_p(signed_dir)
                        if self.align_apk(unsigned_path, signed_path):
                            self.add_failure(platform, locale,
                                             message="Unable to align %(platform)s%(locale)s apk!")
                            self.rmtree(signed_dir)
                        else:
                            success_count += 1
        self.summarize_success_count(success_count, total_count,
                                     message="Signed %d of %d apks successfully.")

    def upload_signed_bits(self):
        self._upload(dir_name="partner-repacks")


# main {{{1
if __name__ == '__main__':
    mobile_partner_repack = MobilePartnerRepack()
    mobile_partner_repack.run()
