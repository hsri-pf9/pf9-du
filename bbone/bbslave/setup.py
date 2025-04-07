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
        'pika==0.13.1',
        'netifaces==0.10.6',
        'py-cpuinfo==7.0.0',
        'psutil==5.6.6',
        'pf9app',
        'bbcommon',
        'configutils',
        'pyyaml==5.4',
        'distro',
        'python-gnupg',
    ],
    test_suite='bbslave',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)
