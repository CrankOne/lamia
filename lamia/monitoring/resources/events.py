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

    def get( self, taskName, procName, _meta=None ):
        """
        Returns events list for certain process.
        """
        L, S = logging.getLogger(__name__), lamia.monitoring.app.db.session
        arrayIndex = flask.request.args.get('arrayIndex', None)
        # ... optional querying
        if arrayIndex is not None:
            p = S.query(models.Array).filter_by( taskID=taskName
                                               , name=procName ).one()
            evs = S.query(models.Event).filter_by( process=p
                                                 , procNumInArray=arrayIndex ).all()
        else:
            p = S.query(models.Process).filter_by( taskID=taskName
                                                 , name=procName ).one()
            evs = S.query(models.Event).filter_by( process=p ).all()
        return schemata.eventSchema.dump(evs, many=True)

    def post( self, vd, _meta=None ):
        """
        Creates new event for certain process.
        """
        resp = {'created' : False}
        L, S = logging.getLogger(__name__), lamia.monitoring.app.db.session
        taskName, procName = vd.pop('processRef')
        arrayIndex = flask.request.args.get('arrayIndex', None)
        if arrayIndex is None:
            j = S.query(models.Process).filter_by( name=procName
                                                 , taskID=taskName).one()
            if j.kin != models.kStandaloneProcess:
                resp['errors'] = [{ 'reason' : 'Is not a standalone process.'
                                  , 'details' : { 'taskName' : taskName
                                                , 'procName' : procName
                                                }
                                  }]
                return resp, 400
            event = models.Event( process=j, **vd )
        else:
            j = S.query(models.Array).filter_by( name=procName
                                               , taskID=taskName).one()
            arrayIndex = int(arrayIndex)
            if arrayIndex > j.nJobs \
            or 0 == arrayIndex:
                resp['errors'] = [{ 'reason' : 'Process index is not in range.'
                                  , 'details' : { 'index' : arrayIndex
                                                , 'nJobs' : j.nJobs
                                                }
                                  }]
                return resp, 400
            if j.kin != models.kArrayProcess:
                resp['errors'] = [{ 'reason' : 'Process is not an array.'
                                  , 'details' : { 'taskName' : taskName
                                                , 'procName' : procName
                                                }
                                  }]
                return resp, 400
            event = models.Event( process=j
                                , procNumInArray=arrayIndex
                                , **vd )
            if _meta:
                if 'time' in _meta:
                    event.submittedAt = _meta['time']
                if 'host' in _meta:
                    event.hostname = _meta['host']
            event.clientIP = flask.request.remote_addr
        S.add( event )
        S.commit()
        resp['created'] = True
        return resp, 201

