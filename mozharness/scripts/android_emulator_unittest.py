#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****

import copy
import os
import sys
import signal
import socket
import subprocess
import telnetlib
import time
import tempfile

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.log import FATAL
from mozharness.base.script import BaseScript
from mozharness.base.vcs.vcsbase import VCSMixin
from mozharness.mozilla.blob_upload import BlobUploadMixin, blobupload_config_options
from mozharness.mozilla.buildbot import TBPL_WORST_LEVEL_TUPLE
from mozharness.mozilla.testing.testbase import TestingMixin, testing_config_options
from mozharness.mozilla.testing.unittest import DesktopUnittestOutputParser, EmulatorMixin
from mozharness.mozilla.tooltool import TooltoolMixin

from mozharness.mozilla.testing.device import ADBDeviceHandler

class AndroidEmulatorTest(BlobUploadMixin, TestingMixin, TooltoolMixin, EmulatorMixin, VCSMixin, BaseScript):
    config_options = [
        [["--robocop-url"],
        {"action": "store",
         "dest": "robocop_url",
         "default": None,
         "help": "URL to the robocop apk",
        }],
        [["--host-utils-url"],
        {"action": "store",
         "dest": "xre_url",
         "default": None,
         "help": "URL to the host utils zip",
        }],
        [["--test-suite"],
        {"action": "append",
         "dest": "test_suites",
        }],
        [["--adb-path"],
        {"action": "store",
         "dest": "adb_path",
         "default": None,
         "help": "Path to adb",
        }],
    ] + copy.deepcopy(testing_config_options) + \
        copy.deepcopy(blobupload_config_options)

    error_list = [
    ]

    virtualenv_requirements = [
    ]

    virtualenv_modules = [
    ]

    app_name = None

    def __init__(self, require_config_file=False):
        super(AndroidEmulatorTest, self).__init__(
            config_options=self.config_options,
            all_actions=['clobber',
                         'read-buildbot-config',
                         'download-cacheable-artifacts',
                         'setup-avds',
                         'start-emulators',
                         'download-and-extract',
                         'create-virtualenv',
                         'install',
                         'run-tests',
                         'stop-emulators'],
            default_actions=['clobber',
                             'download-cacheable-artifacts',
                             'start-emulators',
                             'download-and-extract',
                             'create-virtualenv',
                             'install',
                             'run-tests',
                             'stop-emulators'],
            require_config_file=require_config_file,
            config={
                'virtualenv_modules': self.virtualenv_modules,
                'virtualenv_requirements': self.virtualenv_requirements,
                'require_test_zip': True,
                # IP address of the host as seen from the emulator
                'remote_webserver': '10.0.2.2',
            }
        )

        # these are necessary since self.config is read only
        c = self.config
        abs_dirs = self.query_abs_dirs()
        self.adb_path = c.get('adb_path', self._query_adb())
        self.installer_url = c.get('installer_url')
        self.installer_path = c.get('installer_path')
        self.test_url = c.get('test_url')
        self.test_manifest = c.get('test_manifest')
        self.robocop_url = c.get('robocop_url')
        self.robocop_path = os.path.join(abs_dirs['abs_work_dir'], "robocop.apk")
        self.host_utils_url = c.get('host_utils_url')
        self.minidump_stackwalk_path = c.get("minidump_stackwalk_path")
        self.emulators = c.get('emulators')
        self.test_suite_definitions = c['test_suite_definitions']
        self.test_suites = c.get('test_suites')
        for suite in self.test_suites:
            assert suite in self.test_suite_definitions

    def query_abs_dirs(self):
        if self.abs_dirs:
            return self.abs_dirs
        abs_dirs = super(AndroidEmulatorTest, self).query_abs_dirs()
        dirs = {}
        dirs['abs_test_install_dir'] = os.path.join(
            abs_dirs['abs_work_dir'], 'tests')
        dirs['abs_xre_dir'] = os.path.join(
            abs_dirs['abs_work_dir'], 'hostutils')
        dirs['abs_mochitest_dir'] = os.path.join(
            dirs['abs_test_install_dir'], 'mochitest')
        dirs['abs_modules_dir'] = os.path.join(
            dirs['abs_test_install_dir'], 'modules')
        dirs['abs_reftest_dir'] = os.path.join(
            dirs['abs_test_install_dir'], 'reftest')
        dirs['abs_xpcshell_dir'] = os.path.join(
            dirs['abs_test_install_dir'], 'xpcshell')
        dirs['abs_blob_upload_dir'] = os.path.join(
            abs_dirs['abs_work_dir'], 'blobber_upload_dir')
        for key in dirs.keys():
            if key not in abs_dirs:
                abs_dirs[key] = dirs[key]
        self.abs_dirs = abs_dirs
        return self.abs_dirs

    def _build_arg(self, option, value):
        """
        Build a command line argument
        """
        if not value:
            return []
        return [str(option), str(value)]

    def _redirectSUT(self, emulator_index):
        '''
        This redirects the default SUT ports for a given emulator.
        This is needed if more than one emulator is started.
        '''
        emulator = self.emulators[emulator_index]
        emuport = emulator["emulator_port"]
        sutport1 = emulator["sut_port1"]
        sutport2 = emulator["sut_port2"]
        attempts = 0
        tn = None
        redirect_completed = False
        while attempts < 5:
            if attempts == 0:
               self.info("Sleeping 10 seconds")
               time.sleep(10)
            else:
               self.info("Sleeping 30 seconds")
               time.sleep(30)
            attempts += 1
            self.info("  Attempt #%d to redirect ports: (%d, %d, %d)" % \
                    (attempts, emuport, sutport1, sutport2))
            try:
                tn = telnetlib.Telnet('localhost', emuport, 300)
                break
            except socket.error, e:
                self.info("Trying again after exception: %s" % str(e))
                pass

        if tn != None:
            res = tn.read_until('OK')
            if res.find('OK') == -1:
                self.warning('initial OK prompt not received from emulator: '+str(res))
            tn.write('redir add tcp:' + str(sutport1) + ':' + str(self.config["default_sut_port1"]) + '\n')
            tn.write('redir add tcp:' + str(sutport2) + ':' + str(self.config["default_sut_port2"]) + '\n')
            tn.write('quit\n')
            res = tn.read_all()
            if res.find('OK') == -1:
                self.warning('error adding redirect: '+str(res))
            else:
                redirect_completed = True
        else:
            self.warning('failed to establish a telnet connection with the emulator')
        return redirect_completed

    def _launch_emulator(self, emulator_index):
        emulator = self.emulators[emulator_index]
        env = self.query_env()
        command = [
            "emulator", "-avd", emulator["name"],
            "-debug", "init,console,gles,memcheck,adbserver,adbclient,adb,avd_config,socket",
            "-port", str(emulator["emulator_port"]),
            # Enable kvm; -qemu arguments must be at the end of the command
            "-qemu", "-m", "1024", "-enable-kvm"
        ]
        if "emulator_cpu" in self.config:
            command += ["-qemu", "-cpu", self.config["emulator_cpu"] ]
        tmp_file = tempfile.NamedTemporaryFile(mode='w')
        tmp_stdout = open(tmp_file.name, 'w')
        self.info("Created temp file %s." % tmp_file.name)
        self.info("Trying to start the emulator with this command: %s" % ' '.join(command))
        proc = subprocess.Popen(command, stdout=tmp_stdout, stderr=tmp_stdout, env=env)
        return {
            "process": proc,
            "tmp_file": tmp_file,
            "tmp_stdout": tmp_stdout
            }

    def _check_emulator(self, emulator):
        self.info('Checking emulator %s' % emulator["name"])

        attempts = 0
        tn = None
        contacted_sut = False
        while attempts < 4 and not contacted_sut:
            if attempts != 0:
               self.info("Sleeping 30 seconds")
               time.sleep(30)
            attempts += 1
            self.info("  Attempt #%d to connect to SUT on port %d" % \
                    (attempts, emulator["sut_port1"]))
            try:
                tn = telnetlib.Telnet('localhost', emulator["sut_port1"], 10)
                if tn != None:
                    self.info('Connected to port %d' % emulator["sut_port1"])
                    res = tn.read_until('$>', 10)
                    tn.write('quit\n')
                    if res.find('$>') == -1:
                        self.warning('Unexpected SUT response: %s' % res)
                    else:
                        self.info('SUT response: %s' % res)
                        contacted_sut = True
                    tn.read_all()
                else:
                    self.warning('Unable to connect to the SUT agent on port %d' % emulator["sut_port1"])
            except socket.error, e:
                self.info('Trying again after socket error: %s' % str(e))
                pass
            except EOFError:
                self.info('Trying again after EOF')
                pass
            except:
                self.info('Trying again after unexpected exception')
                pass
            finally:
                if tn != None:
                    tn.close()
        if not contacted_sut:
            self.warning('Unable to communicate with SUT agent on port %d' % emulator["sut_port1"])

        attempts = 0
        tn = None
        contacted_emu = False
        while attempts < 4:
            if attempts != 0:
               self.info("Sleeping 30 seconds")
               time.sleep(30)
            attempts += 1
            self.info("  Attempt #%d to connect to emulator on port %d" % \
                    (attempts, emulator["emulator_port"]))
            try:
                tn = telnetlib.Telnet('localhost', emulator["emulator_port"], 10)
                if tn != None:
                    self.info('Connected to port %d' % emulator["emulator_port"])
                    res = tn.read_until('OK', 10)
                    self.info(res)
                    tn.write('avd status\n')
                    res = tn.read_until('OK', 10)
                    self.info('avd status: %s' % res)
                    tn.write('redir list\n')
                    res = tn.read_until('OK', 10)
                    self.info('redir list: %s' % res)
                    tn.write('network status\n')
                    res = tn.read_until('OK', 10)
                    self.info('network status: %s' % res)
                    tn.write('quit\n')
                    tn.read_all()
                    tn.close()
                    contacted_emu = True
                    break
                else:
                    self.warning('Unable to connect to the emulator on port %d' % emulator["emulator_port"])
            except socket.error, e:
                self.info('Trying again after socket error: %s' % str(e))
                pass
            except EOFError:
                self.info('Trying again after EOF')
                pass
            except:
                self.info('Trying again after unexpected exception')
                pass
            finally:
                if tn != None:
                    tn.close()
        if not contacted_emu:
            self.warning('Unable to communicate with emulator on port %d' % emulator["emulator_port"])

        ps_cmd = [self.adb_path, '-s', emulator["device_id"], 'shell', 'ps']
        p = subprocess.Popen(ps_cmd, stdout=subprocess.PIPE)
        out, err = p.communicate()
        self.info('%s:\n%s\n%s' % (ps_cmd, out, err))

    def _dump_emulator_log(self, emulator_index):
        emulator = self.emulators[emulator_index]
        self.info("##### %s emulator log begins" % emulator["name"])
        output = self.read_from_file(self.emulator_procs[emulator_index]["tmp_file"].name, verbose=False)
        if output:
            self.info(output)
        self.info("##### %s emulator log ends" % emulator["name"])

    def _kill_processes(self, process_name):
        p = subprocess.Popen(['ps', '-A'], stdout=subprocess.PIPE)
        out, err = p.communicate()
        self.info("Let's kill every process called %s" % process_name)
        for line in out.splitlines():
            if process_name in line:
                pid = int(line.split(None, 1)[0])
                self.info("Killing pid %d." % pid)
                os.kill(pid, signal.SIGKILL)

    def _post_fatal(self, message=None, exit_code=None):
        """ After we call fatal(), run this method before exiting.
        """
        self._kill_processes(self.config["emulator_process_name"])

    # XXX: This and android_panda.py's function might make sense to take higher up
    def _download_robocop_apk(self):
        dirs = self.query_abs_dirs()
        self.apk_url = self.installer_url[:self.installer_url.rfind('/')]
        robocop_url = self.apk_url + '/robocop.apk'
        self.info("Downloading robocop...")
        self.download_file(robocop_url, 'robocop.apk', dirs['abs_work_dir'], error_level=FATAL)

    def _query_package_name(self):
        if self.app_name == None:
            #find appname from package-name.txt - assumes download-and-extract has completed successfully
            apk_dir = self.abs_dirs['abs_work_dir']
            self.apk_path = os.path.join(apk_dir, self.installer_path)
            unzip = self.query_exe("unzip")
            package_path = os.path.join(apk_dir, 'package-name.txt')
            unzip_cmd = [unzip, '-q', '-o',  self.apk_path]
            self.run_command(unzip_cmd, cwd=apk_dir, halt_on_failure=True)
            self.app_name = str(self.read_from_file(package_path, verbose=True)).rstrip()
        return self.app_name


    def preflight_install(self):
        # in the base class, this checks for mozinstall, but we don't use it
        pass

    def _build_command(self, emulator, suite_name):
        c = self.config
        dirs = self.query_abs_dirs()
        suite_category = self.test_suite_definitions[suite_name]["category"]
        cmd = [
            self.query_python_path('python'),
            '-u',
            os.path.join(
                dirs["abs_%s_dir" % suite_category],
                c["suite_definitions"][suite_category]["run_filename"]
            ),
        ]

        str_format_values = {
            'app': self._query_package_name(),
            'remote_webserver': c['remote_webserver'],
            'xre_path': os.path.join(dirs['abs_xre_dir'], 'xre'),
            'utility_path':  os.path.join(dirs['abs_xre_dir'], 'bin'),
            'device_ip': c['device_ip'],
            'device_port': str(emulator['sut_port1']),
            'http_port': emulator['http_port'],
            'ssl_port': emulator['ssl_port'],
            'certs_path': os.path.join(dirs['abs_work_dir'], 'tests/certs'),
            # TestingMixin._download_and_extract_symbols() will set
            # self.symbols_path when downloading/extracting.
            'symbols_path': self.symbols_path,
            'modules_dir': dirs['abs_modules_dir'],
            'installer_path': self.installer_path,
        }
        for option in c["suite_definitions"][suite_category]["options"]:
            cmd.extend([option % str_format_values])
        cmd.extend(self.test_suite_definitions[suite_name]["extra_args"])

        return cmd

    def _query_adb(self):
        return self.which('adb') or os.getenv('ADB_PATH')

    def preflight_run_tests(self):
        super(AndroidEmulatorTest, self).preflight_run_tests()

        if not os.path.isfile(self.adb_path):
            self.fatal("The adb binary '%s' is not a valid file!" % self.adb_path)

    def _trigger_test(self, suite_name, emulator_index):
        """
        Run a test suite on an emulator

        We return a dictionary with the following information:
         - subprocess object that is running the test on the emulator
         - the filename where the stdout is going to
         - the stdout where the output is going to
         - the suite name that is associated
        """
        dirs = self.query_abs_dirs()
        cmd = self._build_command(self.emulators[emulator_index], suite_name)
        try:
            cwd = dirs['abs_%s_dir' % self.test_suite_definitions[suite_name]["category"]]
        except:
            self.fatal("Don't know how to run --test-suite '%s'!" % suite_name)

        env = self.query_env()
        self.query_minidump_stackwalk()
        env['MOZ_UPLOAD_DIR'] = self.query_abs_dirs()['abs_blob_upload_dir']
        env['MINIDUMP_SAVE_PATH'] = self.query_abs_dirs()['abs_blob_upload_dir']

        self.info("Running on %s the command %s" % (self.emulators[emulator_index]["name"], subprocess.list2cmdline(cmd)))
        tmp_file = tempfile.NamedTemporaryFile(mode='w')
        tmp_stdout = open(tmp_file.name, 'w')
        self.info("Created temp file %s." % tmp_file.name)
        return {
            "process": subprocess.Popen(cmd, cwd=cwd, stdout=tmp_stdout, stderr=tmp_stdout, env=env),
            "tmp_file": tmp_file,
            "tmp_stdout": tmp_stdout,
            "suite_name": suite_name,
            "emulator_index": emulator_index
            }

    ##########################################
    ### Actions for AndroidEmulatorTest ###
    ##########################################
    def download_cacheable_artifacts(self):
        '''
        This will cache every downloadable artifact specified in
        "tooltool_cacheable_artifacts" to "tooltool_cache_path"
        '''
        c = self.config
        artifacts = c["tooltool_cacheable_artifacts"]
        for artifact_name in artifacts.keys():
            file_name = artifacts[artifact_name][0]
            file_path = os.path.join(c["tooltool_cache_path"], file_name)
            if not os.path.exists(file_path):
                # We store files in tooltool as their shasum representation
                file_shasum = artifacts[artifact_name][1]
                file_url = os.path.join(c["tooltool_url"], file_shasum)
                self.download_file(file_url, file_path, c["tooltool_cache_path"])

    def setup_avds(self):
        '''
        We have a tar ball in ToolTool with the pristine templates.
        Let's unpack them every time.
        '''
        c = self.config
        self.rmtree(c[".avds_dir"])
        avd_tar_ball_path = os.path.join(
                c["tooltool_cache_path"],
                c["tooltool_cacheable_artifacts"]["avd_tar_ball"][0])
        self.mkdir_p(c[".avds_dir"])
        self.unpack(avd_tar_ball_path, c[".avds_dir"])

    def start_emulators(self):
        '''
        This action starts the emulators and redirects the two SUT ports for each one of them
        '''
        assert len(self.test_suites) <= len(self.emulators), \
            "We can't run more tests that the number of emulators we start"
        # We kill compiz because it sometimes prevents us from starting the emulators
        self._kill_processes("compiz")

        attempts = 0
        redirect_failed = True
        # Launch the required emulators and redirect the SUT ports for each. If unable
        # to redirect the SUT ports, kill the emulators and try starting them again.
        # The wait-and-retry logic is necessary because the emulators intermittently fail
        # to respond to telnet connections immediately after startup: bug 949740. In this
        # case, the emulator log shows "ioctl(KVM_CREATE_VM) failed: Interrupted system call".
        # We do not know how to avoid this error and the only way we have found to
        # recover is to kill the emulator and start again.
        while attempts < 3 and redirect_failed:
            if attempts > 0:
                self.info("Sleeping 30 seconds before retry")
                time.sleep(30)
            attempts+=1
            self.info('Attempt #%d to launch emulators...' % attempts)
            self.emulator_procs = []
            emulator_index = 0
            redirect_failed = False
            for test in self.test_suites:
                emulator_proc = self._launch_emulator(emulator_index)
                self.emulator_procs.append(emulator_proc)
                if self._redirectSUT(emulator_index):
                    emulator = self.emulators[emulator_index]
                    self.info("%s: %s; sut port: %s/%s" % \
                        (emulator["name"], emulator["emulator_port"], emulator["sut_port1"], emulator["sut_port2"]))
                    emulator_index+=1
                else:
                    self._dump_emulator_log(emulator_index)
                    self._kill_processes(self.config["emulator_process_name"])
                    redirect_failed = True
                    break
        if redirect_failed:
            self.fatal('We have not been able to establish a telnet connection with the emulator')

        # Verify that we can communicate with each emulator
        emulator_index = 0
        for test in self.test_suites:
            emulator = self.emulators[emulator_index]
            emulator_index+=1
            self._check_emulator(emulator)
        # Start logcat for each emulator. Each adb process runs until the
        # corresponding emulator is killed. Output is written directly to
        # the blobber upload directory so that it is uploaded automatically
        # at the end of the job.
        self.mkdir_p(self.abs_dirs['abs_blob_upload_dir'])
        emulator_index = 0
        for test in self.test_suites:
            emulator = self.emulators[emulator_index]
            emulator_index+=1
            logcat_filename = 'logcat-%s.log' % emulator["device_id"]
            logcat_path = os.path.join(self.abs_dirs['abs_blob_upload_dir'], logcat_filename)
            logcat_cmd = '%s -s %s logcat -v time Trace:S StrictMode:S ExchangeService:S > %s &' % \
                (self.adb_path, emulator["device_id"], logcat_path)
            self.info(logcat_cmd)
            os.system(logcat_cmd)

    def download_and_extract(self):
        # This will download and extract the fennec.apk and tests.zip
        super(AndroidEmulatorTest, self).download_and_extract()
        dirs = self.query_abs_dirs()
        # XXX: Why is it called "download" since we don't download it?
        if self.config.get('download_minidump_stackwalk'):
            # XXX: install_minidump_stackwalk will clone tools regardless if
            # I already have a stackwalk_path on the machine
            # Does it make sense?
            self.install_minidump_stackwalk()

        self._download_robocop_apk()

        self.mkdir_p(dirs['abs_xre_dir'])
        self._download_unzip(self.host_utils_url, dirs['abs_xre_dir'])

    def install(self):
        assert self.installer_path is not None, \
            "Either add installer_path to the config or use --installer-path."

        emulator_index = 0
        for suite_name in self.test_suites:
            emulator = self.emulators[emulator_index]
            emulator_index+=1

            config = {
                'device-id': emulator["device_id"],
                'enable_automation': True,
                'device_package_name': self._query_package_name()
            }
            config = dict(config.items() + self.config.items())

            self.info("Creating ADBDevicHandler for %s with config %s" % (emulator["name"], config))
            dh = ADBDeviceHandler(config=config)
            dh.device_id = emulator['device_id']

            # Install Fennec
            self.info("Installing Fennec for %s" % emulator["name"])
            dh.install_app(self.installer_path)

            # Install the robocop apk if required
            if suite_name.startswith('robocop'):
                self.info("Installing Robocop for %s" % emulator["name"])
                config['device_package_name'] = self.config["robocop_package_name"]
                dh.install_app(self.robocop_path)

            self.info("Finished installing apps for %s" % emulator["name"])

    def run_tests(self):
        """
        Run the tests
        """
        procs = []

        emulator_index = 0
        for suite_name in self.test_suites:
            procs.append(self._trigger_test(suite_name, emulator_index))
            emulator_index+=1

        joint_tbpl_status = None
        joint_log_level = None
        start_time = int(time.time())
        while True:
            for p in procs:
                emulator_index = p["emulator_index"]
                return_code = p["process"].poll()
                if return_code!=None:
                    suite_name = p["suite_name"]
                    # To make reading the log of the suite not mix with the previous line
                    sys.stdout.write('\n')
                    self.info("##### %s log begins" % p["suite_name"])
                    # Let's close the stdout
                    p["tmp_stdout"].close()
                    # Let's read the file that now has the output
                    output = self.read_from_file(p["tmp_file"].name, verbose=False)
                    # Let's parse the output (which also prints it)
                    # and determine what the results should be
                    parser = DesktopUnittestOutputParser(
                                 suite_category=self.test_suite_definitions[p["suite_name"]]["category"],
                                 config=self.config,
                                 log_obj=self.log_obj,
                                 error_list=self.error_list)
                    for line in output.splitlines():
                        parser.parse_single_line(line)

                    # After parsing each line we should know what the summary for this suite should be
                    tbpl_status, log_level = parser.evaluate_parser(return_code)
                    parser.append_tinderboxprint_line(p["suite_name"])
                    # After running all jobs we will report the worst status of all emulator runs
                    joint_tbpl_status = self.worst_level(tbpl_status, joint_tbpl_status, TBPL_WORST_LEVEL_TUPLE)
                    joint_log_level = self.worst_level(log_level, joint_log_level)

                    self.info("##### %s log ends" % p["suite_name"])
                    self._dump_emulator_log(emulator_index)
                    procs.remove(p)
            if procs == []:
                break
            else:
                # Every 5 minutes let's print something to stdout
                # so buildbot won't kill the process due to lack of output
                if int(time.time()) - start_time > 5 * 60:
                    self.info('#')
                    start_time = int(time.time())
                time.sleep(30)

        self.buildbot_status(joint_tbpl_status, level=joint_log_level)

    def stop_emulators(self):
        '''
        Report emulator health, then make sure that every emulator has been stopped
        '''
        emulator_index = 0
        for test in self.test_suites:
            emulator = self.emulators[emulator_index]
            emulator_index+=1
            self._check_emulator(emulator)
        self._kill_processes(self.config["emulator_process_name"])

if __name__ == '__main__':
    emulatorTest = AndroidEmulatorTest()
    emulatorTest.run_and_exit()
