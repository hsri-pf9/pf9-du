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
        'pecan==1.1.2',
        'python-memcached==1.58',
        'keystonemiddleware==4.3.0',
        'babel',
        'sqlalchemy',
        'requests==2.12.5'
    ],
    test_suite='resmgr',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)
