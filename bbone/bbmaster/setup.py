# -*- coding: utf-8 -*-
try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name='bbmaster',
    version='0.1',
    description='',
    author='',
    author_email='',
    install_requires=[
        "pecan==1.1.2",
        "requests==2.11.1",
        "pika==0.10.0",
        "cryptography==1.5",
        "webob==1.7.4",
        "MarkupSafe==1.0",
        "boto3==1.13.19",
        "python-dateutil==2.7.3"
    ],
    test_suite='bbmaster',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)
