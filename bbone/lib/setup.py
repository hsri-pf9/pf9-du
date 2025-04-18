# -*- coding: utf-8 -*-
try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name='bbcommon',
    version='0.1',
    description='',
    author='',
    author_email='',
    install_requires=[
        'requests==2.32.2',
        'urllib3==1.26.19',
        'six==1.16.0'
    ],
    test_suite='bbcommon',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)
