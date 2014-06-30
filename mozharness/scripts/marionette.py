#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****

import copy
import os
import re
import sys

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.errors import TarErrorList, ZipErrorList
from mozharness.base.log import INFO, ERROR, WARNING, FATAL
from mozharness.base.script import PreScriptAction
from mozharness.base.transfer import TransferMixin
from mozharness.base.vcs.vcsbase import MercurialScript
from mozharness.mozilla.blob_upload import BlobUploadMixin, blobupload_config_options
from mozharness.mozilla.buildbot import TBPL_SUCCESS, TBPL_WARNING, TBPL_FAILURE
from mozharness.mozilla.gaia import GaiaMixin
from mozharness.mozilla.testing.errors import LogcatErrorList
from mozharness.mozilla.testing.testbase import TestingMixin, testing_config_options
from mozharness.mozilla.testing.unittest import EmulatorMixin, TestSummaryOutputParserHelper
from mozharness.mozilla.tooltool import TooltoolMixin


class MarionetteOutputParser(TestSummaryOutputParserHelper):
    """
    A class that extends TestSummaryOutputParserHelper such that it can parse
    if gecko did not install properly
    """

    bad_gecko_install = re.compile(r'Error installing gecko!')

    def __init__(self, **kwargs):
        self.install_gecko_failed = False
        super(MarionetteOutputParser, self).__init__(**kwargs)

    def parse_single_line(self, line):
        if self.bad_gecko_install.search(line):
            self.install_gecko_failed = True
        super(MarionetteOutputParser, self).parse_single_line(line)

class MarionetteTest(TestingMixin, TooltoolMixin, EmulatorMixin,
                     MercurialScript, BlobUploadMixin, TransferMixin, GaiaMixin):
    config_options = [
        [["--application"],
         {"action": "store",
          "dest": "application",
          "default": None,
          "help": "application name of binary"
         }],
        [["--gaia-dir"],
         {"action": "store",
          "dest": "gaia_dir",
          "default": None,
          "help": "directory where gaia repo should be cloned"
         }],
        [["--gaia-repo"],
         {"action": "store",
          "dest": "gaia_repo",
          "default": "http://hg.mozilla.org/integration/gaia-central",
          "help": "url of gaia repo to clone"
         }],
        [["--gaia-branch"],
         {"action": "store",
          "dest": "gaia_branch",
          "default": "default",
          "help": "branch of gaia repo to clone"
         }],
        [["--test-type"],
        {"action": "store",
         "dest": "test_type",
         "default": "browser",
         "help": "The type of tests to run",
        }],
        [["--marionette-address"],
        {"action": "store",
         "dest": "marionette_address",
         "default": None,
         "help": "The host:port of the Marionette server running inside Gecko.  Unused for emulator testing",
        }],
        [["--emulator"],
        {"action": "store",
         "type": "choice",
         "choices": ['arm'],
         "dest": "emulator",
         "default": None,
         "help": "Use an emulator for testing",
        }],
        [["--gaiatest"],
        {"action": "store_true",
         "dest": "gaiatest",
         "default": False,
         "help": "Runs gaia-ui-tests by pulling down the test repo and invoking "
                 "gaiatest's runtests.py rather than Marionette's."
        }],
        [["--no-update"],
        {"action": "store_false",
         "dest": "update_files",
         "default": True,
         "help": "Don't update emulator and gecko before running tests"
        }],
        [["--test-manifest"],
        {"action": "store",
         "dest": "test_manifest",
         "default": "unit-tests.ini",
         "help": "Path to test manifest to run relative to the Marionette "
                 "tests directory",
         }],
        [["--xre-path"],
         {"action": "store",
          "dest": "xre_path",
          "default": "xulrunner-sdk",
          "help": "directory (relative to gaia repo) of xulrunner-sdk"
         }],
        [["--xre-url"],
         {"action": "store",
          "dest": "xre_url",
          "default": None,
          "help": "url of desktop xre archive"
         }]] + copy.deepcopy(testing_config_options) + \
               copy.deepcopy(blobupload_config_options)

    error_list = [
        {'substr': 'FAILED (errors=', 'level': WARNING},
        {'substr': r'''Could not successfully complete transport of message to Gecko, socket closed''', 'level': ERROR},
        {'substr': 'Timeout waiting for marionette on port', 'level': ERROR},
        {'regex': re.compile(r'''(Timeout|NoSuchAttribute|Javascript|NoSuchElement|XPathLookup|NoSuchWindow|StaleElement|ScriptTimeout|ElementNotVisible|NoSuchFrame|InvalidElementState|NoAlertPresent|InvalidCookieDomain|UnableToSetCookie|InvalidSelector|MoveTargetOutOfBounds)Exception'''), 'level': ERROR},
    ]

    repos = []

    def __init__(self, require_config_file=False):
        super(MarionetteTest, self).__init__(
            config_options=self.config_options,
            all_actions=['clobber',
                         'read-buildbot-config',
                         'pull',
                         'download-and-extract',
                         'create-virtualenv',
                         'install',
                         'run-marionette'],
            default_actions=['clobber',
                             'pull',
                             'download-and-extract',
                             'create-virtualenv',
                             'install',
                             'run-marionette'],
            require_config_file=require_config_file,
            config={'require_test_zip': True,})

        # these are necessary since self.config is read only
        c = self.config
        self.installer_url = c.get('installer_url')
        self.installer_path = c.get('installer_path')
        self.binary_path = c.get('binary_path')
        self.test_url = c.get('test_url')

    def _pre_config_lock(self, rw_config):
        if not self.config.get('emulator') and not self.config.get('marionette_address'):
                self.fatal("You need to specify a --marionette-address for non-emulator tests! (Try --marionette-address localhost:2828 )")

    def query_abs_dirs(self):
        if self.abs_dirs:
            return self.abs_dirs
        abs_dirs = super(MarionetteTest, self).query_abs_dirs()
        dirs = {}
        dirs['abs_test_install_dir'] = os.path.join(
            abs_dirs['abs_work_dir'], 'tests')
        dirs['abs_marionette_dir'] = os.path.join(
            dirs['abs_test_install_dir'], 'marionette', 'marionette')
        dirs['abs_marionette_tests_dir'] = os.path.join(
            dirs['abs_test_install_dir'], 'marionette', 'tests', 'testing',
            'marionette', 'client', 'marionette', 'tests')
        dirs['abs_gecko_dir'] = os.path.join(
            abs_dirs['abs_work_dir'], 'gecko')
        dirs['abs_emulator_dir'] = os.path.join(
            abs_dirs['abs_work_dir'], 'emulator')

        gaia_root_dir = self.config.get('gaia_dir')
        if not gaia_root_dir:
            gaia_root_dir = self.config['base_work_dir']
        dirs['abs_gaia_dir'] = os.path.join(gaia_root_dir, 'gaia')
        dirs['abs_gaiatest_dir'] = os.path.join(
            dirs['abs_gaia_dir'], 'tests', 'python', 'gaia-ui-tests')
        dirs['abs_blob_upload_dir'] = os.path.join(abs_dirs['abs_work_dir'], 'blobber_upload_dir')

        for key in dirs.keys():
            if key not in abs_dirs:
                abs_dirs[key] = dirs[key]
        self.abs_dirs = abs_dirs
        return self.abs_dirs

    @PreScriptAction('create-virtualenv')
    def _configure_marionette_virtualenv(self, action):
        if self.tree_config.get('use_puppetagain_packages'):
            self.register_virtualenv_module('mozinstall')
            self.register_virtualenv_module('marionette', os.path.join('tests',
                'marionette'))

            return

        dirs = self.query_abs_dirs()
        requirements = os.path.join(dirs['abs_test_install_dir'],
                                    'config',
                                    'marionette_requirements.txt')
        if os.access(requirements, os.F_OK):
            self.register_virtualenv_module(requirements=[requirements],
                                            two_pass=True)
        else:
            # XXX Bug 879765: Dependent modules need to be listed before parent
            # modules, otherwise they will get installed from the pypi server.
            # XXX Bug 908356: This block can be removed as soon as the
            # in-tree requirements files propagate to all active trees.
            mozbase_dir = os.path.join('tests', 'mozbase')
            self.register_virtualenv_module('manifestparser',
                    os.path.join(mozbase_dir, 'manifestdestiny'))
            for m in ('mozfile', 'mozlog', 'mozinfo', 'moznetwork', 'mozhttpd',
                    'mozcrash', 'mozinstall', 'mozdevice', 'mozprofile',
                    'mozprocess', 'mozrunner'):
                self.register_virtualenv_module(m, os.path.join(mozbase_dir,
                    m))

            self.register_virtualenv_module('marionette', os.path.join('tests',
                'marionette'))

        if self.config.get('gaiatest'):
            requirements = os.path.join(self.query_abs_dirs()['abs_gaiatest_dir'],
                                    'tbpl_requirements.txt')
            self.register_virtualenv_module('gaia-ui-tests',
                url=self.query_abs_dirs()['abs_gaiatest_dir'],
                method='pip',
                requirements=[requirements],
                editable=True)

    def pull(self, **kwargs):
        if self.config.get('gaiatest'):
            # clone the gaia dir
            dirs = self.query_abs_dirs()
            dest = dirs['abs_gaia_dir']

            repo = {
              'repo_path': self.config.get('gaia_repo'),
              'revision': 'default',
              'branch': self.config.get('gaia_branch')
            }

            if self.buildbot_config is not None:
                # get gaia commit via hgweb
                repo.update({
                  'revision': self.buildbot_config['properties']['revision'],
                  'repo_path': 'https://hg.mozilla.org/%s' % self.buildbot_config['properties']['repo_path']
                })

            self.clone_gaia(dest, repo,
                            use_gaia_json=self.buildbot_config is not None)

        super(MarionetteTest, self).pull(**kwargs)

    def _build_arg(self, option, value):
        """
        Build a command line argument
        """
        if not value:
            return []
        return [str(option), str(value)]

    def extract_xre(self, filename, parent_dir=None):
        m = re.search('\.tar\.(bz2|gz)$', filename)
        if m:
            # a xulrunner archive, which has a top-level 'xulrunner-sdk' dir
            command = self.query_exe('tar', return_type='list')
            tar_cmd = "jxf"
            if m.group(1) == "gz":
                tar_cmd = "zxf"
            command.extend([tar_cmd, filename])
            self.run_command(command,
                             cwd=parent_dir,
                             error_list=TarErrorList,
                             halt_on_failure=True)
        else:
            # a tooltool xre.zip
            command = self.query_exe('unzip', return_type='list')
            command.extend(['-q', '-o', filename])
            # Gaia assumes that xpcshell is in a 'xulrunner-sdk' dir, but
            # xre.zip doesn't have a top-level directory name, so we'll
            # create it.
            parent_dir = os.path.join(parent_dir,
                                      self.config.get('xre_path'))
            if not os.access(parent_dir, os.F_OK):
                self.mkdir_p(parent_dir, error_level=FATAL)
            self.run_command(command,
                             cwd=parent_dir,
                             error_list=ZipErrorList,
                             halt_on_failure=True)

    def download_and_extract(self):
        super(MarionetteTest, self).download_and_extract()

        if self.config.get('gaiatest'):
            xre_url = self.config.get('xre_url')
            if xre_url:
                dirs = self.query_abs_dirs()
                xulrunner_bin = os.path.join(dirs['abs_gaia_dir'],
                                             self.config.get('xre_path'),
                                             'bin', 'xpcshell')
                if not os.access(xulrunner_bin, os.F_OK):
                    xre = self.download_file(xre_url, parent_dir=dirs['abs_work_dir'])
                    self.extract_xre(xre, parent_dir=dirs['abs_gaia_dir'])

        if self.config.get('emulator'):
            dirs = self.query_abs_dirs()
            if self.config.get('update_files'):
                self.workdir = dirs['abs_work_dir']
                self.install_emulator()
                self.mkdir_p(dirs['abs_gecko_dir'])
                tar = self.query_exe('tar', return_type='list')
                self.run_command(tar + ['zxf', self.installer_path],
                                 cwd=dirs['abs_gecko_dir'],
                                 error_list=TarErrorList,
                                 halt_on_failure=True)
            else:
                self.mkdir_p(dirs['abs_emulator_dir'])
                tar = self.query_exe('tar', return_type='list')
                self.run_command(tar + ['zxf', self.installer_path],
                                 cwd=dirs['abs_emulator_dir'],
                                 error_list=TarErrorList,
                                 halt_on_failure=True)
            if self.config.get('download_minidump_stackwalk'):
                self.install_minidump_stackwalk()

    def install(self):
        if self.config.get('emulator'):
            self.info("Emulator tests; skipping.")
        else:
            super(MarionetteTest, self).install()

    def run_marionette(self):
        """
        Run the Marionette tests
        """
        dirs = self.query_abs_dirs()
        binary = self.binary_path
        manifest = None

        if self.config.get('gaiatest'):
            # make the gaia profile
            self.make_gaia(dirs['abs_gaia_dir'],
                           self.config.get('xre_path'),
                           debug=False,
                           noftu=False)

        # build the marionette command arguments
        python = self.query_python_path('python')
        if self.config.get('gaiatest'):
            # write a testvars.json file
            testvars = os.path.join(dirs['abs_gaiatest_dir'],
                                    'gaiatest', 'testvars.json')
            with open(testvars, 'w') as f:
                f.write("""{"acknowledged_risks": true,
                            "skip_warning": true,
                            "settings": {
                              "time.timezone": "America/Los_Angeles",
                              "time.timezone.user-selected": "America/Los_Angeles"
                            }}
                        """)

            # gaia-ui-tests on B2G desktop builds
            cmd = [python, '-u', os.path.join(dirs['abs_gaiatest_dir'],
                                              'gaiatest',
                                              'cli.py')]

            if not self.config.get('emulator'):
                # support desktop builds with and without a built-in profile
                binary_path = os.path.dirname(self.binary_path)
                binary = os.path.join(binary_path, 'b2g-bin')
                if not os.access(binary, os.F_OK):
                    binary = os.path.join(binary_path, 'b2g')

            cmd.append('--restart')
            cmd.extend(self._build_arg('--type', self.config['test_type']))
            cmd.extend(self._build_arg('--testvars', testvars))
            cmd.extend(self._build_arg('--profile', os.path.join(dirs['abs_gaia_dir'],
                                                                 'profile')))
            cmd.extend(self._build_arg('--symbols-path', self.symbols_path))
            cmd.extend(self._build_arg('--xml-output',
                                       os.path.join(dirs['abs_work_dir'], 'output.xml')))
            cmd.extend(self._build_arg('--html-output',
                                       os.path.join(dirs['abs_blob_upload_dir'], 'output.html')))
            manifest = os.path.join(dirs['abs_gaiatest_dir'], 'gaiatest', 'tests',
                                    'tbpl-manifest.ini')
        else:
            # Marionette or Marionette-webapi tests
            cmd = [python, '-u', os.path.join(dirs['abs_marionette_dir'],
                                              'runtests.py')]

            if self.config.get('emulator'):
                # emulator Marionette-webapi tests
                if self.config.get('update_files'):
                    cmd.extend(self._build_arg('--gecko-path',
                                               os.path.join(dirs['abs_gecko_dir'],
                                                            'b2g')))
                cmd.extend(self._build_arg('--symbols-path', self.symbols_path))

            cmd.extend(self._build_arg('--type', self.config['test_type']))
            manifest = os.path.join(dirs['abs_marionette_tests_dir'],
                                    self.config['test_manifest'])

        if self.config.get('emulator'):
            cmd.extend(self._build_arg('--logcat-dir', dirs['abs_work_dir']))
            cmd.extend(self._build_arg('--emulator', self.config['emulator']))
            cmd.extend(self._build_arg('--homedir',
                                       os.path.join(dirs['abs_emulator_dir'],
                                                    'b2g-distro')))
        else:
            # tests for Firefox or b2g desktop
            cmd.extend(self._build_arg('--binary', binary))
            cmd.extend(self._build_arg('--address',
                                       self.config['marionette_address']))

        cmd.append(manifest)

        env = {}
        if self.query_minidump_stackwalk():
            env['MINIDUMP_STACKWALK'] = self.minidump_stackwalk_path
        if self.config.get('gaiatest'):
            env['GAIATEST_ACKNOWLEDGED_RISKS'] = '1'
            env['GAIATEST_SKIP_WARNING'] = '1'
        env['MOZ_UPLOAD_DIR'] = self.query_abs_dirs()['abs_blob_upload_dir']
        env['MINIDUMP_SAVE_PATH'] = self.query_abs_dirs()['abs_blob_upload_dir']
        if not os.path.isdir(env['MOZ_UPLOAD_DIR']):
            self.mkdir_p(env['MOZ_UPLOAD_DIR'])
        env = self.query_env(partial_env=env)

        for i in range(0, 5):
            # We retry the run because sometimes installing gecko on the
            # emulator can cause B2G not to restart properly - Bug 812935.
            marionette_parser = MarionetteOutputParser(config=self.config,
                                                       log_obj=self.log_obj,
                                                       error_list=self.error_list)
            code = self.run_command(cmd, env=env,
                                    output_timeout=1000,
                                    output_parser=marionette_parser)
            if not marionette_parser.install_gecko_failed:
                break
        else:
            self.fatal("Failed to install gecko 5 times in a row, aborting")

        level = INFO
        if code == 0 and marionette_parser.passed > 0 and marionette_parser.failed == 0:
            status = "success"
            tbpl_status = TBPL_SUCCESS
        elif code == 10 and marionette_parser.failed > 0:
            status = "test failures"
            tbpl_status = TBPL_WARNING
        else:
            status = "harness failures"
            level = ERROR
            tbpl_status = TBPL_FAILURE

        # dump logcat output if there were failures
        if self.config.get('emulator'):
            if marionette_parser.failed != "0" or 'T-FAIL' in marionette_parser.tsummary:
                logcat = os.path.join(dirs['abs_work_dir'], 'emulator-5554.log')
                if os.access(logcat, os.F_OK):
                    self.info('dumping logcat')
                    self.run_command(['cat', logcat], error_list=LogcatErrorList)
                else:
                    self.info('no logcat file found')
        else:
            # .. or gecko.log if it exists
            gecko_log = os.path.join(self.config['base_work_dir'], 'gecko.log')
            if os.access(gecko_log, os.F_OK):
                self.info('dumping gecko.log')
                self.run_command(['cat', gecko_log])
                self.rmtree(gecko_log)
            else:
                self.info('gecko.log not found')

        marionette_parser.print_summary('marionette')

        self.log("Marionette exited with return code %s: %s" % (code, status),
                 level=level)
        self.buildbot_status(tbpl_status)


if __name__ == '__main__':
    marionetteTest = MarionetteTest()
    marionetteTest.run_and_exit()
