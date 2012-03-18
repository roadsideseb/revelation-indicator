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

from DistUtilsExtra.command import *

import revelation_indicator

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


schema_files = glob.glob('data/gconf/*.schemas')

setup(
    name = 'revelation-indicator',
    version = '0.1.0',
    author = 'Sebastian Vetter',
    author_email = 'sebastian@roadside-developer.com',
    #url = '',

    description = '',
    long_description = revelation_indicator.__doc__,
    license = 'GNU General Public License (GPL)',

    scripts = ['bin/revelation-indicator'],
    packages = ['revelation_indicator'],
    provides = [],

    data_files = [
        (sys.prefix+'/share/gconf/schemas', schema_files),
        (sys.prefix+'/share/applications', glob.glob('data/applications/*.desktop')),
    ],
    classifiers = [
        'Development Status :: 4 - Beta',
        'License :: OSI Approved :: GNU General Public License (GPL)',
        'Intended Audience :: Developers',
        'Natural Language :: English',
        'Operating System :: Linux',
        'Programming Language :: Python',
    ],
    cmdclass = { 
        "build" : build_extra.build_extra,
        "install_data": post_install,
        "build_i18n" :  build_i18n.build_i18n,
        "build_help" :  build_help.build_help,
        "build_icons" :  build_icons.build_icons
    },
)

