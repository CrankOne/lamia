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

This module declares schemata for HTTP-based JSON data exchange.

Uses `marshmallow-oneofschema' extension to sustain the sqlalchemy's
polymorphism model:
    https://github.com/marshmallow-code/marshmallow-oneofschema
See relevant discussion on the marsmallow's dev forum:
    https://github.com/marshmallow-code/apispec/pull/182
"""

# extremely useful:
#   https://marshmallow-sqlalchemy.readthedocs.io/en/latest/recipes.html

import logging, json

import marshmallow
import marshmallow.fields
from marshmallow_oneofschema import OneOfSchema
from collections.abc import Iterable

from lamia.monitoring.app import ma, db
from lamia.monitoring.orm import Task, Process, Array, Event
import lamia.monitoring.app

class BaseSchema(ma.ModelSchema):
    class Meta:
        sqla_session = db.session

class ProcessSchema(BaseSchema):
    class Meta(BaseSchema.Meta):
        model = Process

class ArraySchema(BaseSchema):
    class Meta(BaseSchema.Meta):
        model = Array
        #exclude=('id',)

class PolymorphicProcessSchema(OneOfSchema):
    type_schemas = { "solitary" : ProcessSchema
                   , "array" : ArraySchema }
    def get_obj_type( self, obj ):
        if isinstance( obj, Array ):
            return "array"
        elif isinstance( obj, Process ):
            return "solitary"
        else:
            assert(False)

class TaskSchema(BaseSchema):
    processes = marshmallow.fields.Nested( PolymorphicProcessSchema, many=True )

    class Meta(BaseSchema.Meta):
        model = Task

    # Treatment of the `processes' field is somewhat tricky, so we do not
    # rely on marshmallow on creation/serialization of this field.
    @marshmallow.pre_load
    def make_processes(self, data, **kwargs):
        #print(json.dumps(data, sort_keys=True, indent=2))
        if type(data['processes']) in (list, tuple):
            return data
        if 'processes' not in data:
            raise marshmallow.ValidationError( 'Input data must have a "data" key.'
                                             , '_preprocessing' )
        for k, args in data['processes'].items():
            isSingleJob = args is None
            if isSingleJob:
                data['processes'][k] = {'type' : 'solitary'}
                continue
            else:
                if isinstance(args, Iterable):
                    data['processes'][k] = {
                        'type' : 'array',
                        'nJobs' : args[0],
                        'fTolerance' : args[1]
                    }
                else:
                    data['processes'][k] = {
                        'type' : 'array',
                        'nJobs' : args,
                    }
        pl = []
        for k, v in data['processes'].items():
            v['name'] = k
            pl.append(v)
        data['processes'] = pl
        return data

class EventSchema(BaseSchema):
    process = marshmallow.fields.Tuple((
                    marshmallow.fields.String(),
                    marshmallow.fields.String(),
                    marshmallow.fields.Integer(allow_none=True)
                ))

    class Meta(BaseSchema.Meta):
        model = Event

    @marshmallow.pre_load
    def make_process(self, data, **kwargs):
        L, S = logging.getLogger(__name__), lamia.monitoring.app.db.session
        if 'process' in data:
            return data
        L = logging.getLogger(__name__)
        if 'taskName' not in data \
        or 'procName' not in data :
            L.error( json.dumps(data) )
            raise marshmallow.ValidationError( 'Event input data must'
                    ' have "taskName" and "procName" keys.', '_preprocessing' )
        data['process'] = ( data.pop('taskName'), data.pop('procName'), None )
        return data

taskSchema = TaskSchema()
tasksSchema = TaskSchema(many=True)
eventSchema = EventSchema()
eventsSchema = EventSchema(many=True)

