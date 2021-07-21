from setuptools import setup
from catkin_pkg.python_setup import generate_distutils_setup

d = generate_distutils_setup(
    packages=['cfs_msg_gen'],
    scripts=['generate_cfs_messages.py']
)

setup(**d)
