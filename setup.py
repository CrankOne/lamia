import setuptools, re, unittest

"""
Lamia is a script-rendering tool generating scenaries for cluster processing.
"""

def find_version(fname):
    """Attempts to find the version number in the file names fname.
    Raises RuntimeError if not found.
    """
    version = ''
    with open(fname, 'r') as fp:
        reg = re.compile(r'__version__ = [\'"]([^\'"]*)[\'"]')
        for line in fp:
            m = reg.match(line)
            if m:
                version = m.group(1)
                break
    if not version:
        raise RuntimeError('Cannot find version information')
    return version

def get_requirements(fname):
    deps = []
    with open(fname, 'r') as f:
        deps = [ l for l in f if l and '#' != l[0] ]
    return list(deps)

def lamia_test_suite():
    testLoader = unittest.TestLoader()
    testSuite = testLoader.discover('tests', pattern='test_*.py')
    return testSuite

d = {
        'name' : 'lamia_templates',
        'version' : find_version('lamia/__init__.py'),
        'description' : 'Templated script rendering tools.',
        'author' : 'Renat R. Dusaev',
        'license' : 'MIT',
        'long_description' : __doc__,
        'author_email' : 'crank@qcrypt.org',
        'packages' : ['lamia'],
        'url' : 'https://github.com/CrankOne/lamia',
        'install_requires' : get_requirements( 'requirements.txt' ),
        'packages' : setuptools.find_packages(exclude=('tests',)),
        'test_suite' : 'setup.lamia_test_suite',
        'data_files' : [
                ('share/lamia' , [ 'assets/configs/lamia.yaml'
                                 , 'assets/configs/logging.yaml'
                                 , 'assets/configs/rest-srv.yaml'
                                 , 'assets/configs/service' ] )
            ],
        'classifiers' : [
            'Development Status :: 3 - Alpha',
            'Environment :: Console',
            'Environment :: Web Environment',
            'Intended Audience :: Developers',
            'Intended Audience :: System Administrators',
            'Intended Audience :: Science/Research',
            'License :: OSI Approved :: MIT License',
            'Operating System :: POSIX',
            'Programming Language :: Python',
            'Topic :: System :: Clustering',
            'Topic :: Office/Business',
            'Topic :: Software Development :: Pre-processors',
        ]
    }

setuptools.setup( **d )

