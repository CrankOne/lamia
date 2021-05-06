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
See relevant discussion on the marshmallow's dev forum:
    https://github.com/marshmallow-code/apispec/pull/182
"""

# extremely useful:
#   https://marshmallow-sqlalchemy.readthedocs.io/en/latest/recipes.html

import logging, json, re
import datetime
import marshmallow
import marshmallow.fields
import flask_marshmallow.sqla
from marshmallow_oneofschema import OneOfSchema
from collections.abc import Iterable

from flask import current_app as app
from flask_marshmallow import Marshmallow

from lamia.monitoring.orm import db
from lamia.monitoring.orm import Task, Process, Array, Event
import lamia.monitoring.app

ma = Marshmallow(app)

class BaseSchema(ma.SQLAlchemyAutoSchema):  # before marshmallow 0.12 it was ModelSchema
    class Meta:
        sqla_session = db.session
        load_instance = True

class MetaSchema(marshmallow.Schema):
    """
    Schema for `_meta' field accomodating some requests. Consists of host
    self-identification (important, if worker is running in the virtualized
    environment) and request timestamp.
    """
    host = marshmallow.fields.Str()
    time = marshmallow.fields.DateTime()

    @marshmallow.pre_load
    def make_time(self, data, **kwargs):
        # Currently, redundant conversion is done from timestamp to datetime
        # string. For details of how one can handle the timestamp natively,
        # see this discussion on marshmallow dev forum:
        #   https://github.com/marshmallow-code/marshmallow/issues/612
        data['time'] = datetime.datetime.utcfromtimestamp(float(data['time'])) \
                               .isoformat()
        return data

class ProcessSchema(BaseSchema):
    lastEventClass = marshmallow.fields.Str(dump_only=True)

    class Meta(BaseSchema.Meta):
        model = Process
        exclude=('events',)

    _links = ma.Hyperlinks(
        { "events" : ma.URLFor('events', taskName='<taskID>', procName='<name>') },
    )

class ArraySchema(BaseSchema):
    class Meta(BaseSchema.Meta):
        model = Array
        exclude=('events',)

    _links = ma.Hyperlinks(
        { "events" : ma.URLFor('events', taskName='<taskID>', procName='<name>') },
    )

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
        #fields = ('_links',)

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

    _links = ma.Hyperlinks(
        { "self" : ma.URLFor('tasks', name='<name>')
        , "collection" : ma.URLFor('tasks')
        },
    )

class EventSchema(BaseSchema):
    processRef = marshmallow.fields.Tuple([
                    marshmallow.fields.String(),
                    marshmallow.fields.String()
                ])

    class Meta(BaseSchema.Meta):
        model = Event
        exclude = ('process',)

    @marshmallow.pre_load
    def make_process(self, data, **kwargs):
        L, S = logging.getLogger(__name__), db.session
        if 'processRef' in data:
            return data
        L = logging.getLogger(__name__)
        if 'taskName' not in data \
        or 'procName' not in data :
            L.error( json.dumps(data) )
            raise marshmallow.ValidationError( 'Event input data must'
                    ' have "taskName" and "procName" keys.', '_preprocessing' )
        data['processRef'] = ( data.pop('taskName'), data.pop('procName') )
        return data

metaSchema = MetaSchema()
taskSchema = TaskSchema()
tasksSchema = TaskSchema(many=True)
polyProcessSchema = PolymorphicProcessSchema()
arraySchema = ArraySchema()
eventSchema = EventSchema()

