# -*- coding: utf-8 -*-
try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name='pf9app',
    version='0.1',
    description='',
    author='',
    author_email='',
    install_requires=['configutils', 'requests==2.26.0', 'distro'],
    test_suite='pf9app',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)
