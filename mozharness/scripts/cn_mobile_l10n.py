#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****
"""mobile_l10n.py

This currently supports nightly and release single locale repacks for
Android.  This also creates nightly updates.
"""

from copy import deepcopy
import os
import re
import subprocess
import sys

try:
    import simplejson as json
except ImportError:
    import json

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.errors import BaseErrorList, MakefileErrorList
from mozharness.base.log import OutputParser
from mozharness.base.transfer import TransferMixin
from mozharness.mozilla.buildbot import BuildbotMixin
from mozharness.mozilla.release import ReleaseMixin
from mozharness.mozilla.signing import MobileSigningMixin
from mozharness.base.vcs.vcsbase import MercurialScript
from mozharness.mozilla.l10n.locales import LocalesMixin
from mozharness.mozilla.mock import MockMixin


# MobileSingleLocale {{{1
class MobileSingleLocale(MockMixin, LocalesMixin, ReleaseMixin,
                         MobileSigningMixin, TransferMixin,
                         BuildbotMixin, MercurialScript):
    config_options = [[
        ['--locale', ],
        {"action": "extend",
         "dest": "locales",
         "type": "string",
         "help": "Specify the locale(s) to sign and update"
         }
    ], [
        ['--locales-file', ],
        {"action": "store",
         "dest": "locales_file",
         "type": "string",
         "help": "Specify a file to determine which locales to sign and update"
         }
    ], [
        ['--tag-override', ],
        {"action": "store",
         "dest": "tag_override",
         "type": "string",
         "help": "Override the tags set for all repos"
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
        ['--key-alias', ],
        {"action": "store",
         "dest": "key_alias",
         "type": "choice",
         "default": "nightly",
         "choices": ["nightly", "release"],
         "help": "Specify the signing key alias"
         }
    ], [
        ['--this-chunk', ],
        {"action": "store",
         "dest": "this_locale_chunk",
         "type": "int",
         "help": "Specify which chunk of locales to run"
         }
    ], [
        ['--total-chunks', ],
        {"action": "store",
         "dest": "total_locale_chunks",
         "type": "int",
         "help": "Specify the total number of chunks of locales"
         }
    ]]

    def __init__(self, require_config_file=True):
        LocalesMixin.__init__(self)
        MercurialScript.__init__(
            self,
            config_options=self.config_options,
            all_actions=[
                "clobber",
                "pull",
                "list-locales",
                "setup",
                "repack",
                "summary",
            ],
            require_config_file=require_config_file
        )
        self.base_package_name = None
        self.buildid = None
        self.make_ident_output = None
        self.repack_env = None
        self.revision = None
        self.upload_env = None
        self.version = None
        self.upload_urls = {}
        self.locales_property = {}

    # Helper methods {{{2
    def query_repack_env(self):
        if self.repack_env:
            return self.repack_env
        c = self.config
        replace_dict = {}
        if c.get('release_config_file'):
            rc = self.query_release_config()
            replace_dict = {
                'version': rc['version'],
                'buildnum': rc['buildnum']
            }
        repack_env = self.query_env(partial_env=c.get("repack_env"),
                                    replace_dict=replace_dict)
        sc = c.get('sign')
        if sc is None:
            self.fatal("sign configuration not found!")
        signtool_path = os.path.join(sc['signtool_dir'], 'signtool.sh')
        repack_env['MOZ_SIGN_CMD'] = '%s --keystore=%s --password=%s' % (
            signtool_path, sc['keystore_file'], sc['password'])
        self.repack_env = repack_env
        return self.repack_env

    def _query_make_variable(self, variable, make_args=None):
        make = self.query_exe('make')
        env = self.query_repack_env()
        dirs = self.query_abs_dirs()
        if make_args is None:
            make_args = []
        # TODO error checking
        output = self.get_output_from_command_m(
            [make, "echo-variable-%s" % variable] + make_args,
            cwd=dirs['abs_locales_dir'], silent=True,
            env=env
        )
        parser = OutputParser(config=self.config, log_obj=self.log_obj,
                              error_list=MakefileErrorList)
        parser.add_lines(output)
        return output.strip()

    def query_base_package_name(self):
        """Get the package name from the objdir.
        Only valid after setup is run.
        """
        if self.base_package_name:
            return self.base_package_name
        self.base_package_name = self._query_make_variable(
            "PACKAGE",
            make_args=['AB_CD=%(locale)s']
        )
        return self.base_package_name

    def query_version(self):
        """Get the package name from the objdir.
        Only valid after setup is run.
        """
        if self.version:
            return self.version
        c = self.config
        if c.get('release_config_file'):
            rc = self.query_release_config()
            self.version = rc['version']
        else:
            self.version = self._query_make_variable("MOZ_APP_VERSION")
        return self.version

    def add_failure(self, locale, message, **kwargs):
        self.locales_property[locale] = "Failed"
        prop_key = "%s_failure" % locale
        prop_value = self.query_buildbot_property(prop_key)
        if prop_value:
            prop_value = "%s  %s" % (prop_value, message)
        else:
            prop_value = message
        self.set_buildbot_property(prop_key, prop_value, write_to_file=True)
        MercurialScript.add_failure(self, locale, message=message, **kwargs)

    def summary(self):
        MercurialScript.summary(self)
        # TODO we probably want to make this configurable on/off
        locales = self.query_locales()
        for locale in locales:
            self.locales_property.setdefault(locale, "Success")
        self.set_buildbot_property("locales", json.dumps(self.locales_property), write_to_file=True)

    # Actions {{{2
    def pull(self):
        c = self.config
        dirs = self.query_abs_dirs()
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
        self.vcs_checkout_repos(repos, parent_dir=dirs['abs_work_dir'],
                                tag_override=c.get('tag_override'))
        self.pull_locale_source()

    def pull_locale_source(self):
        c = self.config
        parent_dir = self.query_abs_dirs()['abs_l10n_dir']
        self.mkdir_p(parent_dir)

        # Pull locales
        locale_repos = []
        repos = c.get("l10n_repos")
        if not repos:
            self.error("No l10_repos found!")
            return
        for locale in repos:
            # for self.config lock bug
            repo = deepcopy(repos[locale])
            repo["dest"] = os.path.join(parent_dir, locale)
            locale_repos.append(repo)
        revs = self.vcs_checkout_repos(repo_list=locale_repos, 
                                parent_dir=parent_dir,
                                tag_override=c.get('tag_override'))
        self.gecko_locale_revisions = revs

    # list_locales() is defined in LocalesMixin.

    def preflight_setup(self):
        if 'clobber' not in self.actions:
            c = self.config
            if c.get('debug'):
                return
            dirs = self.query_abs_dirs()
            objdir = os.path.join(dirs['abs_work_dir'], c['mozilla_dir'],
                                  c['objdir'])
            self.rmtree(objdir)

    def _build(self):
        c = self.config
        dirs = self.query_abs_dirs()
        env = self.query_repack_env()
        make = self.query_exe("make")
        if self.run_command_m([make, "-f", "client.mk"],
                              cwd=dirs['abs_mozilla_dir'],
                              env=env,
                              error_list=MakefileErrorList):
            self.fatal("Build failed!")
        if self.run_command_m([make, "-f", "client.mk", "package"],
                              cwd=dirs['abs_mozilla_dir'],
                              env=env,
                              error_list=MakefileErrorList):
            self.fatal("Package en-US failed!")

    def setup(self):
        c = self.config
        dirs = self.query_abs_dirs()
        mozconfig_path = os.path.join(dirs['abs_mozilla_dir'], '.mozconfig')
        self.copyfile(os.path.join(dirs['abs_work_dir'], c['mozconfig']),
                      mozconfig_path)
        # TODO stop using cat
        cat = self.query_exe("cat")
        make = self.query_exe("make")
        self.run_command_m([cat, mozconfig_path])
        env = self.query_repack_env()
        # Make the app
        self._build()
        self.run_command_m([make, "unpack"],
                           cwd=dirs['abs_locales_dir'],
                           env=env,
                           error_list=MakefileErrorList,
                           halt_on_failure=True)

    def repack(self):
        # TODO per-locale logs and reporting.
        c = self.config
        dirs = self.query_abs_dirs()
        locales = self.query_locales()
        make = self.query_exe("make")
        repack_env = self.query_repack_env()
        base_package_name = self.query_base_package_name()
        base_package_dir = os.path.join(dirs['abs_objdir'], 'dist')
        output_dir = c["output_dir"]
        # Clear the output folder
        self.rmtree(output_dir)
        self.mkdir_p(output_dir)
        success_count = total_count = 0
        for locale in locales:
            total_count += 1
            self.enable_mock()
            result = self.run_compare_locales(locale)
            self.disable_mock()
            if result:
                self.add_failure(locale, message="%s failed in compare-locales!" % locale)
                continue
            if self.run_command_m([make, "installers-%s" % locale],
                                  cwd=dirs['abs_locales_dir'],
                                  env=repack_env,
                                  error_list=MakefileErrorList,
                                  halt_on_failure=False):
                self.add_failure(locale, message="%s failed in make installers-%s!" % (locale, locale))
                continue
            signed_path = os.path.join(base_package_dir,
                                       base_package_name % {'locale': locale})
            # We need to wrap what this function does with mock, since
            # MobileSigningMixin doesn't know about mock
            self.enable_mock()
            status = self.verify_android_signature(
                signed_path,
                script=c['signature_verification_script'],
                tools_dir=c['tools_dir'],
                env=repack_env,
                key_alias=c['key_alias'],
            )
            self.disable_mock()
            if status:
                self.add_failure(locale, message="Errors verifying %s binary!" % locale)
                # No need to rm because upload is per-locale
                continue
            # Copy the package file to output folder
            output_path = os.path.join(output_dir, base_package_name % {'locale': locale})
            self.copyfile(signed_path, output_path);
            success_count += 1
        self.summarize_success_count(success_count, total_count,
                                     message="Repacked %d of %d binaries successfully.")

# main {{{1
if __name__ == '__main__':
    single_locale = MobileSingleLocale()
    single_locale.run()
