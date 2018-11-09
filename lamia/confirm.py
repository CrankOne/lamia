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

import sys, os

gUserInputPrefix = "\033[32;1;11m\u2593>\033[0m "

class NoDefaultChoice(RuntimeError):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

def get_autoconfirm( varName='AUTOCONFIRM' ):
    envAutoConfirm = os.environ.get('AUTOCONFIRM', False)
    if type(envAutoConfirm) is str:
        if '1' == envAutoConfirm or 'yes' == envAutoConfirm.lower() \
        or 'y' == envAutoConfirm.lower():
            return True
        else:
            return False

def ask_for_confirm( message
                   , default=None ):
    """
    Ask a yes/no question via raw_input() and return their answer.
    "message" is a string that is presented to the user.
    "default" is the presumed answer if the user just hits <Enter>.
        It must be "yes" (the default), "no" or None (meaning
        an answer is required of the user).
    The "answer" return value is True for "yes" or False for "no".
    Automatically returns True when no user input is available.
    """
    envAutoConfirm = get_autoconfirm()
    if not sys.stdin.isatty() or envAutoConfirm:  # TODO:< check this!
        return True
    valid = {"yes": True, "y": True, "ye": True,
             "no": False, "n": False}
    if default is None:
        prompt = " (y/n): "
    elif "yes" == default or 'y' == default:
        prompt = " (Y/n): "
    elif "no" == default or 'n' == default:
        prompt = " (y/N): "
    else:
        raise ValueError("invalid default answer: '%s'" % default)
    while True:
        sys.stdout.write(gUserInputPrefix + message + ' ' + prompt)
        choice = input().lower()
        if default is not None and choice == '':
            return valid[default]
        elif choice in valid:
            return valid[choice]
        else:
            sys.stdout.write("Please respond with 'yes' or 'no' "
                             "(or 'y' or 'n').\n")

def ask_for_variants( message, variants, default=None ):
    """
    Prints the message, awaiting user input. Shall be used instead of simple
    confirmation when multiple choices are expected. Envisages the batch mode.
    Note, that in batch/autoconfirm mode, when no default is provided,
    exception will be raisen.
    """
    envAutoConfirm = get_autoconfirm()
    if not sys.stdin.isatty() or envAutoConfirm:  # TODO:< check this!
        if default is None:
            raise NoDefaultChoice('Default is not set.')  # TODO: custom exception
        return default
    prompt = gUserInputPrefix + message + '\n'
    for k, v in variants.items():
        if default == k:
            prompt += gUserInputPrefix + ' [\033[1m%s\033[0m]: %s\n'%(k, v)
        else:
            prompt += gUserInputPrefix + '  \033[1m%s\033[0m: %s\n'%(k, v)
    prompt += gUserInputPrefix
    while True:
        sys.stdout.write(prompt)
        choice = input()
        if default is not None and choice == '':
            return default
        elif choice in variants:
            return choice
        else:
            sys.stdout.write("Please respond with one of %s.\n"%('/'.join(variants.keys())))
