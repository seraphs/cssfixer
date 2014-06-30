HOME = "/home/cewang/cssfixer/"
SIGN_PASSWORD = "mozilla"
BUILD_HOME = HOME
DOWNLOAD_BASE_URL = HOME
APK_BASE_NAME = "fennec-%(version)s.%(locale)s.android-arm.apk"
KEYSTORE = "%stest.keystore" % BUILD_HOME
KEY_ALIAS = "release"

config = {
    "version":30,
    "locales":["en-US"],
    "debug": False,
    "files_directory": HOME,
    "workdir": "%srepack_work" % BUILD_HOME,
    "distribution_dir":	"%sdistribution" % BUILD_HOME,
    "output_dir": "%soutput" % BUILD_HOME,
    "log_name": "cssfixer_repack",
    "platforms": ["android"],
    "installer_base_names": {
        "android": APK_BASE_NAME,
    },
    "download_base_url": DOWNLOAD_BASE_URL,
    "inserted_files": ["browser.js", "bootstrap.js", "css-browserside.js"],
    "default_actions": [ "download", "repack", "sign", "upload-signed-bits", "summary"],

    "release_config_file": "%srelease-fennec-mozilla-release.py" % BUILD_HOME,
    # signing (optional)
    "keystore": KEYSTORE,
    "key_alias": KEY_ALIAS,
    "sign_password": SIGN_PASSWORD,
    "tools_dir": "%stools/" % BUILD_HOME,
    "signature_verification_script": "%stools/release/signing/verify-android-signature.sh" % BUILD_HOME,
    "exes": {
    "zipalign": "%szipalign" % HOME,
    },
}
