# -*- coding: utf-8 -*-
try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name='bbslave',
    version='0.1',
    description='',
    author='',
    author_email='',
    install_requires=[
        'pika',
        'pf9app',
        'bbcommon',
        'configutils',
        'netifaces'
    ],
    test_suite='bbslave',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)
