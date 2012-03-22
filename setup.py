#! /usr/bin/env python
# -*- coding: utf-8 -*-
#
# revelation-indicator
# Copyright (C) 2012 Sebastian Vetter
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License

import os
import sys
import pwd
import glob
import subprocess

from distutils.core import setup
from distutils.command.install_data import install_data


class post_install(install_data):

    def run(self):
        # Call parent
        install_data.run(self)

        if pwd.getpwuid(os.getuid()).pw_name == 'root':
            # Execute commands
            config_source = subprocess.check_output([
                'gconftool-2',
                '--get-default-source'
            ]).strip()
            for schema_file in [os.path.basename(f) for f in schema_files]:
                cmd = ' '.join([
                    "GCONF_CONFIG_SOURCE=%s" % config_source,
                    "gconftool-2",
                    "--makefile-install-rule",
                    sys.prefix+'/share/gconf/schemas/'+schema_file
                ])
                output = subprocess.check_output(cmd, shell=True)


def get_icons(icon_dir):
    data_files = []

    for size in glob.glob(os.path.join(icon_dir, "*")):
        for category in glob.glob(os.path.join(size, "*")):
            icons = []
            for icon in glob.glob(os.path.join(category,"*")):
                icons.append(icon)
                data_files.append((
                    "share/icons/hicolor/%s/%s" % (
                        os.path.basename(size),
                        os.path.basename(category)
                    ),
                    icons
                ))
    return data_files


schema_files = glob.glob('data/gconf/*.schemas')

setup(
    name = 'revelation-indicator',
    version = '0.1.1',
    author = 'Sebastian Vetter',
    author_email = 'sebastian@roadside-developer.com',
    url = 'https://github.com/elbaschid/revelation-indicator',

    description = 'Indicator for the revelation password manager on Unity desktop.',
    long_description = open('README.rst').read(),
    license = 'GNU General Public License (GPL)',

    scripts = ['bin/revelation-indicator'],
    packages = ['revelation_indicator'],
    provides = [],

    data_files = [
        (sys.prefix+'/share/gconf/schemas', schema_files),
        (sys.prefix+'/share/applications', glob.glob('data/applications/*.desktop')),
    ] + get_icons('data/icons/'),
    classifiers = [
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Intended Audience :: End Users/Desktop',
        'Natural Language :: English',
        'Operating System :: POSIX :: Linux',
        'Environment :: X11 Applications :: GTK',
        'Environment :: X11 Applications :: Gnome',
        'Programming Language :: Python',
        'Topic :: Utilities',
        'Topic :: Security :: Cryptography',
        'Topic :: Desktop Environment :: Gnome',
    ],
    cmdclass = {
        "install_data": post_install,
    },
)
