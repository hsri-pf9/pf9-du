# -*- coding: utf-8 -*-
try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(
    name='pf9cert',
    version='0.1',
    description='',
    author='',
    author_email='',
    install_requires=[
        'pyOpenSSL==16.1.0',
        "cryptography==1.5"
    ],
    test_suite='pf9cert',
    zip_safe=False,
    include_package_data=True,
    package_data={'pf9cert': [
        'root_ca_template/*.txt',
        'root_ca_template/*.cnf',
        'root_ca_template/serial',
        'root_ca_template/certs/*',
        'root_ca_template/private/*',
        'root_ca_template/svc/*'
    ]},
    packages=find_packages(exclude=['ez_setup'])
)
