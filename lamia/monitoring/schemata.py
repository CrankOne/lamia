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
Lamia provides rudimentary support for monitoring of the running processes via
RESTful API. This module declares object relational model for running tasks.

This module declares common schemata for HTTP-based JSON data exchange.
"""
import schema, datetime, calendar
from email.utils import parsedate_tz as parsedate_  # the RFC 5322 is standard here

def parsedate(dt):
    return datetime.datetime.fromtimestamp(calendar.timegm(parsedate_(dt)))

# Schema of incoming `event' message.
gEventSchema = schema.Schema({
        'from' : schema.Or( schema.And(str, len)
                          , [str, str, schema.Use(int)] ),
        'type' : schema.And( str, lambda s : s in {'submit', 'started', 'beat', 'term'} ),
        schema.Optional('rc') : schema.Use(int),
        schema.Optional('completion') : schema.Or( schema.And(schema.Use(int), lambda n: 0 <= n <= 100 )
                                                 , [schema.Use(int), schema.Use(int)] ),
        schema.Optional('payload') : lambda o: type(o) is dict  # arbitrary dict
    })

# Schema of incoming `new task' message.
gTaskSchema = schema.Schema({
        'label' : str,
        'config' : lambda o: type(o) is dict,  # arbitrary dict
        'submitted' : schema.Use(parsedate),
        schema.Optional('depGraph') : str,
        schema.Optional('jobs') : [ str ],
        schema.Optional('arrays') : { str : schema.Or( schema.And(int, lambda n: n > 1)
                                                     , [ schema.And(int, lambda n: n > 1), schema.And(int, lambda n: n > 1) ] ) }
    })

