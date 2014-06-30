MOZ_UPDATE_CHANNEL = "release"
SIGN_PASSWORD = "Password is required to sign the APK file"
HOME = "/home/moz/"
BUILD_HOME = "%sfennec/" % HOME
MOZILLA_DIR = "%sgecko" % BUILD_HOME
OBJDIR = "%sobjdir-droid" % BUILD_HOME
HG_SHARE_BASE_DIR = BUILD_HOME

config = {
    "debug": False,
    "log_name": "single_locale",
    "objdir": OBJDIR,
    "output_dir": "%soutput" % BUILD_HOME,
    "locales_dir": "mobile/android/locales",
    "locales_platform": "android",
    "locales": ["zh-CN"],
    "ignore_locales": ["en-US"],
    "exes":{
        "gittool.py": "%stools/buildfarm/utils/gittool.py" % BUILD_HOME
    },
    "repos": [{
        "repo": "ssh://git@223.202.6.29/repository/git/mobile-android/mozilla-central.git",
        "vcs": "gittool",
        "vcs_share_base": None,
        "branch": "cn_fennec_release",
        "dest": MOZILLA_DIR,
    },{
        "repo": "ssh://git@223.202.6.29/repository/git/mobile-android/buildbot-configs.git",
        "vcs": "gittool",
        "vcs_share_base": None,
        "branch": "master",
        "dest": "%sbuildbot-configs" % BUILD_HOME
    },{
        "repo": "ssh://git@223.202.6.29/repository/git/mobile-android/build-tools.git",
        "vcs": "gittool",
        "vcs_share_base": None,
        "branch": "cn",
        "dest": "%stools" % BUILD_HOME
    },{
        "repo": "ssh://git@223.202.6.29/repository/git/mobile-android/compare-locales.git",
        "vcs": "gittool",
        "branch": "master",
        "vcs_share_base": None
    }],
    "l10n_repos": {
        "zh-CN": {
        "repo": "ssh://git@223.202.6.29/repository/git/mobile-android/mozilla-l10n-zh-CN.git",
        "vcs": "gittool",
        "vcs_share_base": None,
        "branch": "mozilla-release",
        }
    },
    "vcs_share_base": HG_SHARE_BASE_DIR,
    "l10n_dir": MOZILLA_DIR,
    "release_config_file": "%sbuildbot-configs/mozilla/release-fennec-mozilla-release.py" % BUILD_HOME,
    "repack_env": {
        "MOZ_PKG_VERSION": "%(version)s",
        "MOZ_OBJDIR": OBJDIR,
        "LOCALE_MERGEDIR": "%(abs_merge_dir)s/",
        "MOZ_UPDATE_CHANNEL": MOZ_UPDATE_CHANNEL,
    },
    "sign": {
        "signtool_dir": "%stools/release/signing/" % BUILD_HOME,
        "keystore_file": "%sMozillaOnlineReleaseKey.keystore" % BUILD_HOME,
        "password": SIGN_PASSWORD
    },
    "merge_locales": True,
    "make_dirs": ['config'],
    "mozilla_dir": MOZILLA_DIR,
    "mozconfig": "%s/mobile/android/config/mozconfigs/android/l10n-release" % MOZILLA_DIR,
    "tools_dir": "%stools/" % BUILD_HOME,
    "signature_verification_script": "%stools/release/signing/verify-android-signature.sh" % BUILD_HOME,
    "key_alias": "release",
    "default_actions": [
        "clobber",
        "pull",
        "list-locales",
        "setup",
        "repack",
        "summary",
    ]
}
