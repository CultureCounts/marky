from __future__ import print_function
from setuptools import setup, find_packages
import io
import codecs
import os
import sys

import marky

here = os.path.abspath(os.path.dirname(__file__))

def read(*filenames, **kwargs):
    encoding = kwargs.get('encoding', 'utf-8')
    sep = kwargs.get('sep', '\n')
    buf = []
    for filename in filenames:
        with io.open(filename, encoding=encoding) as f:
            buf.append(f.read())
    return sep.join(buf)

long_description = read('README')

setup(
    name='marky',
    version='0.0.1',
    url='https://github.com/rubzo/marky',
    license='',
    author='Stephen Kyle',
    tests_require=['pytest'],
    install_requires=[],
    author_email='',
    description='A benchmark execution and statistics gathering framework',
    long_description=long_description,
    packages=['marky'],
    include_package_data=True,
    platforms='any',
    classifiers = [
        'Programming Language :: Python',
        'Development Status :: 3 - alpha',
        'Natural Language :: English',
        'Environment :: Web Environment',
        'Intended Audience :: CC Developers',
        'Operating System :: OS Independent',
        'Topic :: Software Development :: Libraries :: Python Modules',
        'Topic :: Software Development :: Libraries :: Application Frameworks',
        'Topic :: Internet :: WWW/HTTP :: Dynamic Content',
        ],
    extras_require={}
)