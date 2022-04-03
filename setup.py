"""Setup.py for Huma SDK"""

from setuptools import setup, find_packages

# Pull in the package info
package_name = 'huma'
package = __import__(package_name)
version = package.__version__
author = package.__author__
email = package.__email__

setup(
    name=package_name,
    version=version,
    description='Huma CLI Tool',
    author=author,
    author_email=email,
    maintainer=author,
    maintainer_email=email,
    packages=find_packages(),
    include_package_data=True,
    install_requires=[
        'boto3',
        'requests',
        'huma_sdk@git+ssh://git@github.com/humahq/huma-sdk.git@9cb01800be20767c9f1f362dbfb7ab9b3c5dbd53#egg=huma_sdk&subdirectory=huma_sdk',
        'click',
        'deepdiff',
        'Flask',
        'ruamel.yaml',
        'pygments'
    ],
    license='Proprietary',
    keywords='',
    classifiers=[
        'Development Status :: 2 - Pre-Alpha',
        'Intended Audience :: Developers',
        'License :: Proprietary',
        'Natural Language :: English',
        'Programming Language :: Python :: 3.8',
        'Programming Language :: Python :: Implementation :: CPython'
    ],
    entry_points='''
        [console_scripts]
        huma=huma.menu:cli
    '''
)
