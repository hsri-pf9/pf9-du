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
        "pecan==1.5.0",
        "WebTest==2.0.35",
        "requests==2.32.3",
        "urllib3==2.3.0",
        "pika==0.13.1",
        "cryptography==44.0.2",
        "webob==1.8.9",
        "MarkupSafe==2.0.1",
        "boto3==1.15.18",
        "botocore==1.18.18"
    ],
    test_suite='bbmaster',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
)
