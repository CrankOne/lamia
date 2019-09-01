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
Helper classes and utility functions are to be defined here.
"""

import flask, schema, logging, inspect
import sqlalchemy.orm.exc
import lamia.monitoring.app

def validate_input( inputSchema ):
    """
    Parameterized decorator performing validation of input data (JSON)
    against provided marshmellow schema.

    If data is valid, it will be provided as a first argument to the forwarded
    (decorated) function.

    Upon failure returns 400 JSON object with { 'error' : ..., 'details' : ... }
    fields.

    TODO: support XML?
    """
    def _json_input( f ):
        #vSchema = inputSchema.get( f.__n )
        hasSchema = f.__name__.upper() in inputSchema
        # Do a trick: extract the names from the function signature to build a
        # named dictionary from basic URL arguments and append the JSON data
        # with them to conjugate info into a single object
        signature = inspect.Signature.from_callable(f)
        # TODO: it is hard to understand which ones are cought by Werkzeug, but
        # details available:
        #   - https://werkzeug.palletsprojects.com/en/0.15.x/routing/
        # note there a `MapAdapter' section that explains mechanism in details.
        argNames = tuple( (p.name, p.default is not inspect.Parameter.empty ) \
                     for nm, p in signature.parameters.items() \
                         if p.kind in ( inspect.Parameter.POSITIONAL_ONLY
                                      , inspect.Parameter.POSITIONAL_OR_KEYWORD) )
        def _f( *args, **kwargs ):
            L = logging.getLogger(__name__)
            try:
                if not hasSchema:
                    L.warning( 'No input schema defined for method "{method}"'
                        ' of the resource "{resourceName}."'.format(
                                        method=flask.request.method,
                                        resourceName=f.__name__.upper() # TODO: retrieve class name?
                                    ) )
                    return f( *args, **kwargs )
                vd = flask.request.get_json()
                for k in list(kwargs.keys()):
                    if not k.startswith('_'):
                        vd[k] = kwargs.pop(k)
                argsNamesSet = set( p[0] for p in argNames )
                if '_meta' in argsNamesSet:
                    # TODO: valudate meta info vs. schema:
                    kwargs['_meta'] = vd.pop('_meta', None)
                if '_data' in argsNamesSet:
                    kwargs['_data'] = vd
                if '_schema' in argsNamesSet:
                    kwargs['_schema'] = inputSchema[flask.request.method]
                vd.update(dict((k, v) for k, v in kwargs.items() if not k.startswith('_') ))
                errors = inputSchema[flask.request.method].validate( vd )
                if errors:
                    # Upon errors appeared, return the list
                    return { 'errors' : [ { 'reason' : 'Input data invalid.'
                                          , 'details' : errors }
                                        ]
                           }, 400
                return f( vd, *args, **kwargs )
            except schema.SchemaError as e:
                L.exception(e)
                return { 'errors' : [ { 'reason' : 'Input data validation failure.'
                                      , 'details' : str(e) }
                                    ]
                       } , 400
            except sqlalchemy.orm.exc.NoResultFound as e:
                L.exception(e)
                return { 'errors' : [ { 'reason' : 'No data found for query.'
                                      , 'details' : str(e) }
                                    ]
                       } , 404
            except ValueError as e:
                L.exception(e)
                return { 'errors' : [ { 'reason' : 'Input data error.'
                                      , 'details' : str(e) }
                                    ]
                       } , 400
            except Exception as e:
                L.exception(e)
                return { 'errors' : [ { 'reason' : 'Generic server error.'
                                      , 'details' : str(e) }
                                    ]
                       }, 500
        #_f.__name__ = f.__name__
        return _f
    return _json_input

