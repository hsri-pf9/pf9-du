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
        "typing-extensions==4.1.1",
        "pecan==1.4.0",
        "requests==2.26.0",
        "pika==0.10.0",
        "cryptography==3.3.2",
        "webob==1.8.7",
        "MarkupSafe==2.0.1",
        "boto3==1.18.28"
    ],
    test_suite='bbmaster',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)
