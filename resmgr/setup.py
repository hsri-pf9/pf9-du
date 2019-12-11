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
        'alembic',
        'pecan',
        'keystonemiddleware',
        'python-memcached',
        'sqlalchemy',
        'requests',
        'mysqlclient',
        'Paste',
        'PasteDeploy',
        'prometheus-client==0.7.1'
    ],
    test_suite='resmgr',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)
