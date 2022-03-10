try:
    from setuptools import setup, find_packages
except ImportError:
    from ez_setup import use_setuptools
    use_setuptools()
    from setuptools import setup, find_packages

setup(name='pf9_du_tests',
      version='0.1',
      author='Platform9',
      author_email='support@platform9.net',
      install_requires=[
        # sorted list helps spot duplicates during merge conflicts
        'proboscis',
      ],
      packages=find_packages())
