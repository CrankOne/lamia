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
from lamia.monitoring.orm import db
import flask, logging, json
import lamia.monitoring.app
import lamia.monitoring.utils
import lamia.monitoring.schemata as schemata

class Events(flask_restful.Resource):
    method_decorators = [validate_input({'POST': schemata.eventSchema})]

    def get( self, taskName, procName, _meta=None, id=None ):
        """
        Returns events list for certain process.
        """
        L, S = logging.getLogger(__name__), db.session
        arrayIndex = None
        if flask.request.args:
            rqa = flask.request.args.to_dict()
            s = schemata.EventsQuerySchema()
            errors = s.validate(rqa)
            L.debug('Event query parameters to be validated: ' + str(rqa))
            if errors:
                L.debug('Event validation errors: ' + str(errors))
                return {'errors': errors}, 400
            qp = s.load(rqa)
            arrayIndex = qp.get('arrayIndex', None)
        else:
            qp = {}
            arrayIndex = None
        #arrayIndex = flask.request.args.get('arrayIndex', None)
        # ... optional querying
        if arrayIndex is not None:
            procQ = S.query(models.Array)
        else:
            procQ = S.query(models.Process)
        # Get the process/array instance
        p = procQ.filter_by(taskID=taskName, name=procName).one_or_none()
        if p is None:
            L.debug(f'Process not found: taskName="{taskName}",'
                    f' procName="{procName}", arrayIndex={arrayIndex}')
            return {'errors': ['Process not found.']}, 404
        q = S.query(models.Event)
        if arrayIndex is None:
            q = q.filter_by(process=p)
        else:
            q = q.filter_by(process=p, procNumInArray=int(arrayIndex))
        if 'fields' in qp:
            q = q.options(sqlalchemy.orm.load_only(*[f for f in qp['fields']]))
            # ^^^ TODO: seems to not work...
        for k in ['eventClass', 'hostname', 'ip']:
            if k in qp:
                q = q.filter_by(**{k:qp[k]})
        if not id:
            q, nTotal = lamia.monitoring.utils.apply_pagination(q, qp, models.Event)
            return { 'entries': schemata.eventSchema.dump(q.all(), many=True)
                   , 'total': nTotal }
        else:
            try:
                e = q.filter_by(id=id).scalar()
            except:
                if not e: return {'errors': ['Event not found.']}, 404
            return schemata.eventSchema.dump(e)

    def post( self, vd, _meta=None ):
        """
        Creates new event for certain process.
        """
        resp = {'created' : False}
        L, S = logging.getLogger(__name__), db.session
        taskName, procName = vd.pop('processRef')
        arrayIndex = flask.request.args.get('arrayIndex', None)
        L.debug( f'Events POST: {taskName}/{procName} with arrayIndex=' + str(arrayIndex) )
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
                                               , taskID=taskName).one_or_none()
            if not j:
                resp['errors'] = [{ 'reason' : 'Process array does not exist.'
                                  , 'details' : {'processName': procName } }]
                return resp, 400
            arrayIndex = int(arrayIndex)
            if arrayIndex > j.nJobs \
            or 0 > arrayIndex:
                resp['errors'] = [{ 'reason' : 'Process index is not within the range.'
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
                    event.sentAt = _meta['time']
                if 'host' in _meta:
                    event.hostname = _meta['host']
            event.clientIP = flask.request.remote_addr
        S.add( event )
        S.commit()
        resp['created'] = True
        # TODO: check the fTolerance/thrProgress
        return resp, 201

