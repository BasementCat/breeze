#!/usr/bin/env python
import os
from setuptools import setup

def read(filen):
    with open(os.path.join(os.path.dirname(__file__), filen), "r") as fp:
        return fp.read()
 
config = dict(
    name="breeze",
    version="0.1a",
    description="Assemble static sites",
    long_description=read("README.md"),
    author="Alec Elton",
    author_email="alec.elton@gmail.com",
    url="http://git.dev.nilcat.com/gateway-furmeet/breeze",
    packages=["breeze"],
    install_requires=[
        'PyYAML', 'jinja2', 'markdown'
    ],
    test_suite="nose.collector",
    tests_require=["nose"],
)

if __name__ == "__main__":
    setup(**config)