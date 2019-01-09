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

import flask, schema, logging
import sqlalchemy.orm.exc

def validate_input( inputSchema ):
    """
    Parameterized decorator performing validation of input data (JSON)
    against provided python schema.

    If data is valid, it will be provided as a first argument to the forwarded
    (decorated) function.

    Upon failure returns 400 JSON object with { 'error' : ..., 'details' : ... }
    fields.

    TODO: support XML?
    """
    def _json_input( f ):
        def _f( *args, **kwargs ):
            L = logging.getLogger(__name__)
            try:
                if flask.request.method in inputSchema \
                and inputSchema[flask.request.method] is not None:
                    # TODO: support XML?
                    vd = inputSchema[flask.request.method].validate( flask.request.get_json() )
                else:
                    if flask.request.method in inputSchema \
                    and inputSchema[flask.request.method] is not None:
                        L.warning( 'No input schema defined for method "{method}" of the '
                            'resource "{resourceName}."'.format(
                                method=flask.request.method,
                                resourceName=f.__name__ ) )
                    else:
                        # The schema is explicitly set to None, no data to transfer
                        # from request
                        return f( *args, **kwargs )
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

