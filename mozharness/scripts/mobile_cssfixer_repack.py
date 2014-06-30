#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****
"""repack_config.py

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
    config_options = []

    def __init__(self, require_config_file=True):
        self.release_config = {}
        LocalesMixin.__init__(self)
        MercurialScript.__init__(
            self,
            config_options=self.config_options,
            all_actions=[
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

    def _repack_apk(self,orig_path, repack_path, version):
        """ Repack the apk with a partner update channel.
        Returns True for success, None for failure
        """
        c = self.config
        zip_bin = self.query_exe("zip")
        unzip_bin = self.query_exe("unzip")
        file_name = os.path.basename(orig_path)
        tmp_dir = os.path.join(self.config['work_dir'], 'tmp')
        tmp_file = os.path.join(tmp_dir, file_name)
        tmp_chrome_content_dir = os.path.join(tmp_dir,"chrome","chrome", "content")
        # Error checking for each step.
        # Ignoring the mkdir_p()s since the subsequent copyfile()s will
        # error out if unsuccessful.
        if self.rmtree(tmp_dir):
            return
        self.mkdir_p(tmp_chrome_content_dir)
        if self.copyfile(orig_path, tmp_file):
            return

        if self.run_command([unzip_bin, '-q', file_name, 'assets/omni.ja'],
                            error_list=ZipErrorList,
                            return_type='num_errors',
                            cwd=tmp_dir):
            self.error("Can't extract omni.ja from %s!" % file_name)
            return

        for target_file in c['inserted_files']:
            origin_file = c['files_directory']
            if self.copyfile("%s%s" % (origin_file, target_file), "%s/%s" % (tmp_chrome_content_dir, target_file)):
                self.error("Can't find file %s in %s" % (target_file, origin_file))
            else:
                 if self.run_command([zip_bin, '-0r', 'assets/omni.ja',
                             'chrome/chrome/content/%s' % target_file],
                            error_list=ZipErrorList,
                            return_type='num_errors',
                            cwd=tmp_dir):
                    self.error("Can't add %s to omni.ja!" % target_file)
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
                repack_path = os.path.join(c['workdir'], 'unsigned/%s/%s/%s' % (platform, locale, installer_name))
                total_count += 1
                if self._repack_apk(original_path, repack_path, rc['version']):
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
                signed_path = os.path.join(c['workdir'], 'signed/%s/%s/%s' % (platform, locale, installer_name))
                dest_path = os.path.join(output_dir, installer_name)
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
                unsigned_path = os.path.join(c['workdir'], 'unsigned/%s/%s/%s' % (platform, locale, installer_name))
                signed_dir = os.path.join(c['workdir'], 'signed/%s/%s/' % (platform, locale))
                signed_path = os.path.join(signed_dir, installer_name)
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
