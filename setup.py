from distribute_setup import use_setuptools
use_setuptools()

from setuptools import setup


setup(
    name='clustering',
    version='0.1.0',
    author='Louis-Philippe Theriault',
    author_email='lpther@gmail.com',
    packages=['clustering'],
    url='https://github.com/lpther/Clustering.git',
    license='See LICENSE.txt',
    description='',
    long_description=open('README.txt').read(),
)
