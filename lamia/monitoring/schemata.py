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
import schema, datetime, calendar, enum, itertools, re
from email.utils import parsedate_tz as parsedate_  # the RFC 5322 is standard here

rxNsTimestamp = re.compile(r'\d+\.\d+')

def parsedate(dt):
    if rxNsTimestamp.match(dt):
        # this is probably timestamp with nanoseconds ($ date +%s.%N)
        return datetime.datetime.fromtimestamp(float(dt))
    else:
        # otherwise, assume the string being in RFC 5322 format
        return datetime.datetime.fromtimestamp(calendar.timegm(parsedate_(dt)))

_EV_TYPES = {
    1: ['submitted',    'SUBM'],
    2: ['started',      'STRT'],
    3: ['beat',         'BEAT'],
    4: ['terminated',   'TERM'],
}

RemProcEventType = enum.Enum(
    value='RemProcEventType',
    names=itertools.chain.from_iterable(
        itertools.product(v, [k]) for k, v in _EV_TYPES.items()
    )
)

def event_type_from_str(s):
    return dict( (v[0], RemProcEventType[v[1]]) for k, v in _EV_TYPES.items() )[s]

gMetaSignature = schema.Schema({
        'time' : schema.Use(parsedate),
        'host' : str
    })

updateEventSchema = schema.Schema({
    '!meta' : gMetaSignature,
    'type' : schema.And( str
                       , lambda s : s.lower() in set([v[0] for v in _EV_TYPES.values()])
                       , schema.Use( event_type_from_str ) ),
    schema.Optional('exitCode') : schema.Use(int),
    schema.Optional('payload') : lambda o: type(o) is dict  # arbitrary dict
})

# Schema of incoming `event' message.  XXX?
eventSchema = {
    'POST' : schema.Schema({
        '!meta' : gMetaSignature,
        'from' : schema.Or( schema.And(str, len)
                          , [str, str, schema.Use(int)] ),
        'type' : schema.And( str
                           , lambda s : s.lower() in set(v[0] for v in _EV_TYPES.values())
                           , schema.Use( event_type_from_str ) ),
        schema.Optional('exitCode') : schema.Use(int),
        schema.Optional('payload') : lambda o: type(o) is dict  # arbitrary dict
    }),
    # ...
}

# Schemata of single/array jobs (remote processes) requests
procSchema = {
    'POST' : schema.Schema({
        '!meta' : gMetaSignature,
    }),
    'PUT' : updateEventSchema
}

# Schemata of single/array jobs (remote processes) requests
arraySchema = {
    'POST' : schema.Schema({
        '!meta' : gMetaSignature,
        'nJobs' : schema.And( schema.Use(int), lambda s: int(s) > 0 ),
        'tolerance' : schema.And( schema.Use(int), lambda s: int(s) > 0 ),
    }),
}

# Schema of incoming `new task' message.
taskSchema = {
    'POST' : schema.Schema({
        '!meta' : gMetaSignature,
        'label' : str,
        'typeLabel' : str,
        'config' : lambda o: type(o) is dict,  # arbitrary dict
        schema.Optional('depGraph') : str,
        schema.Optional('jobs') : [ str ],
        schema.Optional('arrays') : { str : schema.Or( schema.And(int, lambda n: n > 1)
                                                     , [ schema.And(int, lambda n: n > 1), schema.And(int, lambda n: n > 1) ] ) }
    }),
    # ...
}

# The "term" schema. Could be defined:
#   - as a scalar value (i.a. string)
#   - as a range: [<from>, <to>] or ["<=", <val>]

# Schemata of incoming search/lookup requests
searchSchema = schema.Schema({
        '!meta' : gMetaSignature,
        'subject' : schema.And(str, lambda s: s in {'task', 'event', 'array', 'job'}),
        'terms' : { str : str },
        'values' : [ str ],
        schema.Optional('order') : [ str ]
    })
