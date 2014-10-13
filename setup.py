from setuptools import setup

setup(
    name='beets-check',
    version='0.9.3',
    description='beets plugin verifying file integrity with checksums',
    long_description=open('README.md').read(),
    author='Thomas Scholtes',
    author_email='thomas-scholtes@gmx.de',
    url='http://www.github.com/geigerzaehler/beets-check',
    license='MIT',
    platforms='ALL',

    test_suite='test',

    packages=['beetsplug'],

    install_requires=[
        'beets>=1.3.7',
        'futures',
    ],

    classifiers=[
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Multimedia :: Sound/Audio :: Players :: MP3',
        'License :: OSI Approved :: MIT License',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Programming Language :: Python :: 2',
        'Programming Language :: Python :: 2.6',
        'Programming Language :: Python :: 2.7',
    ],
)
