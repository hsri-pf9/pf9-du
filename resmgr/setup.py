# -*- coding: utf-8 -*-
try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name='resmgr',
    version='0.1',
    description='',
    author='',
    author_email='',
    install_requires=[
        'python-daemon==1.6.1',
        'alembic',
        'pecan',
        'keystonemiddleware',
        'python-memcached',
        'sqlalchemy',
        'requests',
        'MySQL-python',
        'Paste',
        'PasteDeploy'
    ],
    test_suite='resmgr',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)
