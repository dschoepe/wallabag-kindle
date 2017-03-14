from setuptools import setup, find_packages
from codecs import open
from os import path

here = path.abspath(path.dirname(__file__))

with open(path.join(here, 'README.org'), encoding='utf-8') as f:
    long_description = f.read()

setup(
    name='wallabag_kindle',
    version='0.0.1',
    description='A tool for sending wallabag articles to a kindle',
    long_description=long_description,
    url='https://github.com/pypa/sampleproject',
    author='Daniel Schoepe',
    author_email='daniel@schoepe.org',
    license='GPLv3',
    classifiers=[
        'Development Status :: 3 - Alpha',
        'Intended Audience :: System Administrators',
        'Topic :: Internet :: WWW/HTTP :: WSGI :: Application',
        'License :: OSI Approved :: GNU General Public License v3 (GPLv3)',
        'Programming Language :: Python :: 3',
        'Programming Language :: Python :: 3.3',
        'Programming Language :: Python :: 3.4',
        'Programming Language :: Python :: 3.5',
    ],
    keywords='wallabag kindle',
    packages=find_packages(exclude=['contrib', 'docs', 'tests']),
    install_requires=['ebooklib', 'bs4'],
    extras_require={
    },
    package_data={
    },
    data_files=[
    #    ('wallabag-kindle.ini', ['doc/wallabag-kindle/wallabag-kindle.ini.example'])
    ],
    entry_points={
    },
    include_package_data=True,
)
