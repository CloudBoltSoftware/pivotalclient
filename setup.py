from distutils.core import setup

VERSION = '0.1'

setup(
    name='pivotalclient',
    packages=['pivotalclient'],
    version=VERSION,
    description='A Python pivotal tracker client.',
    author='Taylor J. Meek, CloudBolt Software',
    author_email='taylor+pypi@cloudbolt.io',
    url='https://github.com/CloudBoltSoftware/pivotalclient',
    download_url='https://github.com/CloudBoltSoftware/pivotalclient/tarball/{version}'.format(version=VERSION),
    keywords=['pivotal', 'api', 'rest', 'client'],
    license='MIT',
    long_description=open('README').read(),
    classifiers=[],
    py_modules=['pivotalclient'],
)
