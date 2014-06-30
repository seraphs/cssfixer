# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****

# This is a template config file for web-platform-tests test.

config = {
    "options": [
        "--metadata-root=%(test_path)s/metadata"
    ],
    "default_actions": [
        'clobber',
        'download-and-extract',
        'create-virtualenv',
        'pull',
        'install',
        'run-tests',
    ],
}

