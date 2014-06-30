import os
import platform

#### OS Specifics ####
ABS_WORK_DIR = os.path.join(os.getcwd(), 'build')
BINARY_PATH = os.path.join(ABS_WORK_DIR, "firefox", "firefox-bin")
INSTALLER_PATH = os.path.join(ABS_WORK_DIR, "installer.tar.bz2")
XPCSHELL_NAME = "xpcshell"
DISABLE_SCREEN_SAVER = True
ADJUST_MOUSE_AND_SCREEN = False
if platform.architecture()[0] == '64bit':
    MINIDUMP_STACKWALK_PATH = "%(abs_work_dir)s/tools/breakpad/linux64/minidump_stackwalk"
else:
    MINIDUMP_STACKWALK_PATH = "%(abs_work_dir)s/tools/breakpad/linux/minidump_stackwalk"

#####
config = {
    ### BUILDBOT
    "buildbot_json_path": "buildprops.json",
    "exes": {
        'python': '/tools/buildbot/bin/python',
        'virtualenv': ['/tools/buildbot/bin/python', '/tools/misc-python/virtualenv.py'],
    },
    "find_links": [
        "http://pypi.pvt.build.mozilla.org/pub",
        "http://pypi.pub.build.mozilla.org/pub",
    ],
    "pip_index": False,
    ###
    "installer_path": INSTALLER_PATH,
    "binary_path": BINARY_PATH,
    "xpcshell_name": XPCSHELL_NAME,
    "run_file_names": {
        "mochitest": "runtests.py",
        "reftest": "runreftest.py",
        "xpcshell": "runxpcshelltests.py",
        "cppunittest": "runcppunittests.py",
        "jittest": "jit_test.py"
    },
    "minimum_tests_zip_dirs": ["bin/*", "certs/*", "modules/*", "mozbase/*", "config/*"],
    "specific_tests_zip_dirs": {
        "mochitest": ["mochitest/*"],
        "reftest": ["reftest/*", "jsreftest/*"],
        "xpcshell": ["xpcshell/*"],
        "cppunittest": ["cppunittests/*"],
        "jittest": ["jit-test/*"]
    },
    "reftest_options": [
        "--appname=%(binary_path)s", "--utility-path=tests/bin",
        "--extra-profile-file=tests/bin/plugins", "--symbols-path=%(symbols_path)s"
    ],
    "mochitest_options": [
        "--appname=%(binary_path)s", "--utility-path=tests/bin",
        "--extra-profile-file=tests/bin/plugins", "--symbols-path=%(symbols_path)s",
        "--certificate-path=tests/certs", "--autorun", "--close-when-done",
        "--console-level=INFO", "--setpref=webgl.force-enabled=true"
    ],
    "xpcshell_options": [
        "--symbols-path=%(symbols_path)s",
        "--test-plugin-path=%(test_plugin_path)s"
    ],
    "cppunittest_options": [
        "--symbols-path=%(symbols_path)s",
        "--xre-path=%(abs_app_dir)s"
    ],
    "jittest_options": [
        "tests/bin/js",
        "--tinderbox",
        "--tbpl"
    ],
    #local mochi suites
    "all_mochitest_suites": {
        "plain1": ["--total-chunks=5", "--this-chunk=1", "--chunk-by-dir=4"],
        "plain2": ["--total-chunks=5", "--this-chunk=2", "--chunk-by-dir=4"],
        "plain3": ["--total-chunks=5", "--this-chunk=3", "--chunk-by-dir=4"],
        "plain4": ["--total-chunks=5", "--this-chunk=4", "--chunk-by-dir=4"],
        "plain5": ["--total-chunks=5", "--this-chunk=5", "--chunk-by-dir=4"],
        "chrome": ["--chrome"],
        "browser-chrome": ["--browser-chrome"],
        "browser-chrome-1": ["--browser-chrome", "--total-chunks=3", "--this-chunk=1"],
        "browser-chrome-2": ["--browser-chrome", "--total-chunks=3", "--this-chunk=2"],
        "browser-chrome-3": ["--browser-chrome", "--total-chunks=3", "--this-chunk=3"],
        "a11y": ["--a11y"],
        "plugins": ['--setpref=dom.ipc.plugins.enabled=false',
                    '--setpref=dom.ipc.plugins.enabled.x86_64=false',
                    '--ipcplugins']
    },
    #local reftest suites
    "all_reftest_suites": {
        "reftest": ["tests/reftest/tests/layout/reftests/reftest.list"],
        "crashtest": ["tests/reftest/tests/testing/crashtest/crashtests.list"],
        "jsreftest": ["--extra-profile-file=tests/jsreftest/tests/user.js", "tests/jsreftest/tests/jstests.list"],
        "reftest-ipc": {'env': {'MOZ_OMTC_ENABLED': '1',
                                'MOZ_DISABLE_CONTEXT_SHARING_GLX': '1'},
                        'options': ['--setpref=browser.tabs.remote=true',
                                    '--setpref=layers.offmainthreadcomposition.testing.enabled=true',
                                    'tests/reftest/tests/layout/reftests/reftest-sanity/reftest.list']},
        "reftest-no-accel": ['--setpref=layers.acceleration.force-enabled=disabled',
                             'tests/reftest/tests/layout/reftests/reftest.list'],
        "crashtest-ipc": {'env': {'MOZ_OMTC_ENABLED': '1',
                                  'MOZ_DISABLE_CONTEXT_SHARING_GLX': '1'},
                          'options': ['--setpref=browser.tabs.remote=true',
                                      '--setpref=layers.offmainthreadcomposition.testing.enabled=true',
                                      'tests/reftest/tests/testing/crashtest/crashtests.list']},
    },
    "all_xpcshell_suites": {
        "xpcshell": ["--manifest=tests/xpcshell/tests/all-test-dirs.list",
                     "%(abs_app_dir)s/" + XPCSHELL_NAME]
    },
    "all_cppunittest_suites": {
        "cppunittest": ['tests/cppunittests']
    },
    "all_jittest_suites": {
        "jittest": []
    },
    "run_cmd_checks_enabled": True,
    "preflight_run_cmd_suites": [
        # NOTE 'enabled' is only here while we have unconsolidated configs
        {
            "name": "disable_screen_saver",
            "cmd": ["xset", "s", "off", "s", "reset"],
            "halt_on_failure": False,
            "architectures": ["32bit", "64bit"],
            "enabled": DISABLE_SCREEN_SAVER
        },
        {
            "name": "run mouse & screen adjustment script",
            "cmd": [
                # when configs are consolidated this python path will only show
                # for windows.
                "python", "../scripts/external_tools/mouse_and_screen_resolution.py",
                "--configuration-url",
                "http://hg.mozilla.org/%(branch)s/raw-file/%(revision)s/" +
                    "testing/machine-configuration.json"],
            "architectures": ["32bit"],
            "halt_on_failure": True,
            "enabled": ADJUST_MOUSE_AND_SCREEN
        },
    ],
    "repos": [{"repo": "http://hg.mozilla.org/build/tools"}],
    "vcs_output_timeout": 1000,
    "minidump_stackwalk_path": MINIDUMP_STACKWALK_PATH,
    "minidump_save_path": "%(abs_work_dir)s/../minidumps",
    "buildbot_max_log_size": 52428800,
    "default_blob_upload_servers": [
         "https://blobupload.elasticbeanstalk.com",
    ],
    "blob_uploader_auth_file" : os.path.join(os.getcwd(), "oauth.txt"),
}
