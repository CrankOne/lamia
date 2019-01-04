# -*- coding: utf-8 -*-
# Copyright (c) 2018 Renat R. Dusaev <crank@qcrypt.org>
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

"""
Set of constructors that creates new entities on database.

The need of dedicated module for this ctrs originates from their sophisticated
relations.
"""

import flask_restful
import lamia.monitoring.orm as models
from lamia.monitoring.resources import validate_input
import flask, logging, json, schema
import lamia.monitoring.app
import lamia.monitoring.schemata as schemata

def new_remote_proc_event( vd ):
    if 'terminated' == vd['type']:
        return models.RemProcTerminated( timestamp=vd['!meta']['time']
                                       , ev_type=vd['type']
                                       , completion=vd.get('exitCode', None) )
    elif 'beat' == vd['type']:
        return models.RemProcBeatProgress( timestamp=vd['!meta']['time']
                                         , ev_type=vd['type']
                                         , completion=vd.get('exitCode', None) )
    else:
        return models.RemProcEvent( timestamp=vd['!meta']['time']
                                  , ev_type=vd['type'] )

