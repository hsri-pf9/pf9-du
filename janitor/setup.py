#
# Copyright (c) 2014 Platform 9 Systems, All rights reserved.
#

# -*- coding: utf-8 -*-
try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name='janitor',
    version='0.1',
    description='General purpose maintenance task executor',
    author='pf9',
    author_email='pf9@platform9.net',
    install_requires=[
        "python-daemon",
        "requests"
    ],
    test_suite='janitor',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)

