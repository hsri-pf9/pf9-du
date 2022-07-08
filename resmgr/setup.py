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
        'firkinize',
        'keystonemiddleware',
        'python-memcached',
        'sqlalchemy',
        'requests',
        'mysqlclient',
        'Paste',
        'PasteDeploy',
        'prometheus-client==0.7.1',
        'pycryptodome',
        'jaeger_client==3.10.0',
        'opentracing_instrumentation==2.4.3'
        #'opentracing==1.3.0' 
        # opentracing_instrumentation==2.4.3 will fetch opentracing==1.3.0 as a dependency
    ],
    test_suite='resmgr',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)
