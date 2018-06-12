#!/usr/bin/env python
import os
from setuptools import setup

# HAX - vboxsf filesystem won't allow hardlinks, so...
del os.link

def read(filen):
    with open(os.path.join(os.path.dirname(__file__), filen), "r") as fp:
        return fp.read()
 
config = dict(
    name="libbreeze",
    version="0.5b",
    description="Assemble static sites",
    long_description=read("README.md"),
    author="Alec Elton",
    author_email="alec.elton@gmail.com",
    url="https://github.com/BasementCat/breeze",
    packages=["breeze"],
    install_requires=[
        'PyYAML', 'jinja2', 'markdown', 'arrow', 'libsass', 'cchardet', 'python-magic',
    ],
    test_suite="nose.collector",
    tests_require=["nose", "mock"],
)

if __name__ == "__main__":
    setup(**config)