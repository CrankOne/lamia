# -*- coding: utf-8 -*-
# Copyright (c) 2017 Renat R. Dusaev <crank@qcrypt.org>
# Author: Renat R. Dusaev <crank@qcrypt.org>
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

import os, logging, logging.config, yaml

gColoredPrfxs = {
        logging.CRITICAL : "\033[41;1;11m\u2592E\033[0m",
        logging.ERROR    : "\033[31;1;11m\u2591e\033[0m",
        logging.WARNING  : "\033[33;1;11m\u2591w\033[0m",
        logging.INFO     : "\033[34;1;11m\u2591i\033[0m",
        logging.DEBUG    : "\033[34;2;11m\u2591D\033[0m",
        logging.NOTSET   : "\033[31;2;11m\u2591?\033[0m"
    }

class ConsoleColoredFormatter(logging.Formatter):
    def format( self, record ):
        m = super(ConsoleColoredFormatter, self).format(record)
        m = gColoredPrfxs[record.levelno] + ' ' + m
        return m

def setup( defaultPath='logging.yaml'
         , defaultLevel=logging.DEBUG
         , envKey='LAMIA_LOG_CFG' ):
    """
    Setup logging configuration.
    Note, that for `root' logger the level will be set to DEBUG once the global
    shell variable is set.
    """
    path = defaultPath
    value = os.getenv(envKey, None)
    if value:
        path = value
    if os.path.exists(path):
        with open(path, 'rt') as f:
            config = yaml.safe_load(f.read())
        if os.getenv('DEBUG', None):
            config['root']['level'] = 'DEBUG'
        logging.config.dictConfig(config)
    else:
        logging.basicConfig(level=defaultLevel)

