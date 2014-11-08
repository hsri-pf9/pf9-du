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
        "python-daemon",
        "alembic",
        "pecan",
        "sqlalchemy",
        'requests'
    ],
    test_suite='resmgr',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)

# FIXME: Because of
# https://bitbucket.org/pypa/setuptools/issue/73/typeerror-dist-must-be-a-distribution
# python-keystone client has to be installed with a separate 'pip install'.
