from setuptools import setup

setup(
    name='beets-check',
    version='0.13.0',
    description='beets plugin verifying file integrity with checksums',
    long_description=open('README.md').read(),
    long_description_content_type='text/markdown',
    author='Thomas Scholtes',
    author_email='thomas-scholtes@gmx.de',
    url='http://www.github.com/geigerzaehler/beets-check',
    license='MIT',
    platforms='ALL',

    test_suite='test',

    packages=['beetsplug'],

    python_requires='>=3.7',
    install_requires=[
        'beets>=1.4.7',
    ],

    classifiers=[
        'Topic :: Multimedia :: Sound/Audio',
        'Topic :: Multimedia :: Sound/Audio :: Players :: MP3',
        'License :: OSI Approved :: MIT License',
        'Environment :: Console',
        'Environment :: Web Environment',
        'Programming Language :: Python :: 3',
    ],
)
