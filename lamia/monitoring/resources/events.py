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
Entities reflects the events happening with the particular process.
Their lyfecycle does not imply direct deletion or update.

Insertion of event must be performed with PATCH'ing corresponding job instance.
"""

import sqlalchemy
import flask_restful
import lamia.monitoring.orm as models
from lamia.monitoring.resources import validate_input
import flask, logging, json, schema
import lamia.monitoring.app
import lamia.monitoring.schemata as schemata

class Events(flask_restful.Resource):
    method_decorators = [validate_input({'POST': schemata.eventSchema})]
    #def get( self, e, _meta=None ):
    #    raise NotImplementedError()

    def post( self, vd, _meta=None ):
        resp = {'created' : False}
        L, S = logging.getLogger(__name__), lamia.monitoring.app.db.session
        taskName, jobName, jobIndex = vd.pop('process')
        t = S.query(models.Task).filter_by(name=taskName).one_or_none()
        if not t:
            resp['errors'] = [{ 'reason' : 'Event corresponds to unknwon task.'
                              , 'details' : taskName }]
            return resp, 404
        if jobIndex is None:
            j = S.query(models.Process).filter_by(name=jobName, task=t).one_or_none()
        else:
            j = S.query(models.Process).filter_by(name=jobName, task=t).one_or_none()
        if j is None:
            resp['errors'] = [{ 'reason' : 'Event corresponds to unknown process.'
                              , 'details' : jobName }]
            return resp, 404
        event = models.Event( process=j
                            , **vd )
        S.add( event )
        S.commit()
        resp['created'] = True
        return resp, 201

