
try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages


setup(
    name='notifier',
    version='0.1',
    description='',
    author='',
    author_email='',
    install_requires=['pika'],
    test_suite='notifier',
    zip_safe=False,
    include_package_data=True,
    packages=find_packages(exclude=['ez_setup'])
    )
