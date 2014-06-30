HOME = "/home/moz/"
SIGN_PASSWORD = "Password is required to sign the APK file"
BUILD_HOME = "%sfennec/" % HOME
DOWNLOAD_BASE_URL = "%soutput/" % BUILD_HOME
APK_BASE_NAME = "fennec-%(version)s.%(locale)s.android-arm.apk"
HG_SHARE_BASE_DIR = BUILD_HOME
KEYSTORE = "%sMozillaOnlineReleaseKey.keystore" % BUILD_HOME
KEY_ALIAS = "release"

config = {
    "debug": True,
    "workdir": "%spartner_work" % BUILD_HOME,
    "output_dir": "%spartner_output" % BUILD_HOME,
    "log_name": "partner_repack",
    "locales": ["zh-CN"],
    "platforms": ["android"],
    "repos": [{
        "repo": "ssh://git@223.202.6.29/repository/git/mobile-android/buildbot-configs.git",
        "vcs": "gittool",
        "vcs_share_base": None,
        "branch": "master",
        "dest": "%sbuildbot-configs" % BUILD_HOME,
    },{
        "repo": "ssh://git@223.202.6.29/repository/git/mobile-android/build-tools.git",
        "vcs": "gittool",
        "vcs_share_base": None,
        "branch": "cn",
        "dest": "%stools" % BUILD_HOME,
    }],
    'vcs_share_base': HG_SHARE_BASE_DIR,
    "installer_base_names": {
        "android": APK_BASE_NAME,
    },
    "partner_config": {
        "google": {},
        "baidu": {},
        "hiapk": {},
        "gfan": {},
        "znzhi": {},
        "appchina": {},
        "myapp": {},
        "nduo": {},
        "xm": {},
        "wandoujia": {},
        "91zs": {},
        "360zs": {},
        "terminal": {},
        "operator": {},
        "website-m": {},
        "website-w": {},
    },
    "download_base_url": DOWNLOAD_BASE_URL,

    "release_config_file": "%sbuildbot-configs/mozilla/release-fennec-mozilla-beta.py" % BUILD_HOME,

    "default_actions": ["pull", "download", "repack", "sign", "upload-signed-bits", "summary"],

    # signing (optional)
    "keystore": KEYSTORE,
    "key_alias": KEY_ALIAS,
    "sign_password": SIGN_PASSWORD,
    "tools_dir": "%stools/" % BUILD_HOME,
    "signature_verification_script": "%stools/release/signing/verify-android-signature.sh" % BUILD_HOME,
    "exes": {
        "zipalign": "%sandroid-sdk/tools/zipalign" % HOME,
        "gittool.py": "%stools/buildfarm/utils/gittool.py" % BUILD_HOME,
    },
}
