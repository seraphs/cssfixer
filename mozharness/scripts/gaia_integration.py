#!/usr/bin/env python
# ***** BEGIN LICENSE BLOCK *****
# This Source Code Form is subject to the terms of the Mozilla Public
# License, v. 2.0. If a copy of the MPL was not distributed with this file,
# You can obtain one at http://mozilla.org/MPL/2.0/.
# ***** END LICENSE BLOCK *****

import os
import sys

# load modules from parent dir
sys.path.insert(1, os.path.dirname(sys.path[0]))

from mozharness.base.gaia_test import GaiaTest
from mozharness.mozilla.testing.unittest import TestSummaryOutputParserHelper


class GaiaIntegrationTest(GaiaTest):
    def __init__(self, require_config_file=False):
      GaiaTest.__init__(self, require_config_file)

    def run_tests(self):
        """
        Run the integration test suite.
        """
        dirs = self.query_abs_dirs()

        output_parser = TestSummaryOutputParserHelper(
          config=self.config, log_obj=self.log_obj, error_list=self.error_list)

        # Copy the b2g desktop we built to the gaia directory so that it
        # gets used by the marionette-js-runner.
        self.copytree(
            os.path.join(dirs['abs_work_dir'], 'b2g'),
            os.path.join(dirs['abs_gaia_dir'], 'b2g'),
            overwrite='clobber'
        )

        self.run_command(['npm', 'cache', 'clean'])

        # `make test-integration \
        #      MOCHA_REPORTER=mocha-tbpl-reporter \
        #      NPM_REGISTRY=http://npm-mirror.pub.build.mozilla.org`
        code = self.run_command([
            'make',
            'test-integration',
            'NPM_REGISTRY=' + self.config.get('npm_registry'),
            'REPORTER=mocha-tbpl-reporter',
            'TEST_MANIFEST=./shared/test/integration/tbpl-manifest.json'
        ], cwd=dirs['abs_gaia_dir'],
           output_parser=output_parser,
           output_timeout=330)

        # Dump npm-debug.log, if it exists
        npm_debug = os.path.join(dirs['abs_gaia_dir'], 'npm-debug.log')
        if os.access(npm_debug, os.F_OK):
            self.info('dumping npm-debug.log')
            self.run_command(['cat', npm_debug])

        output_parser.print_summary('gaia-integration-tests')
        self.publish(code)

if __name__ == '__main__':
    gaia_integration_test = GaiaIntegrationTest()
    gaia_integration_test.run_and_exit()
