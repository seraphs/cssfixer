#!/usr/bin/env python
# -*- coding: utf-8 -*-

import os
import sys
import requests
from requests.compat import is_py3, is_py2

try:
    from setuptools import setup
except ImportError:
    from distutils.core import setup



if sys.argv[-1] == 'publish':
    os.system('python setup.py sdist upload')
    sys.exit()

if sys.argv[-1] == 'test':
    os.system('python test_requests.py')
    sys.exit()

required = ['certifi>=0.0.7',]
packages = [
    'requests',
    'requests.packages',
    'requests.packages.urllib3',
    'requests.packages.urllib3.packages',
    'requests.packages.urllib3.packages.ssl_match_hostname',
    'requests.packages.urllib3.packages.mimetools_choose_boundary',
]

if is_py3:
    required.append('chardet2')
else:
    required.append('chardet>=1.0.0')
    packages.append('requests.packages.oreos')


setup(
    name='requests',
    version=requests.__version__,
    description='Python HTTP for Humans.',
    long_description=open('README.rst').read() + '\n\n' +
                     open('HISTORY.rst').read(),
    author='Kenneth Reitz',
    author_email='me@kennethreitz.com',
    url='http://python-requests.org',
    packages=packages,
    package_data={'': ['LICENSE', 'NOTICE']},
    include_package_data=True,
    install_requires=required,
    license='ISC',
    classifiers=(
        'Development Status :: 5 - Production/Stable',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'License :: OSI Approved :: ISC License (ISCL)',
        'Programming Language :: Python',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.0',
        'Programming Language :: Python :: 3.1',
    ),
)
