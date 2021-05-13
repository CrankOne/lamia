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
View defining tasks as a resource.

No HATEOAS currently implemented.
"""

import flask_restful
import sqlalchemy
import lamia.monitoring.orm as models
import flask, logging, json
import lamia.monitoring.app
from lamia.monitoring.resources import validate_input
import lamia.monitoring.schemata as schemata
from lamia.monitoring.orm import db

class Tasks(flask_restful.Resource):
    method_decorators = [validate_input({'POST' : schemata.taskSchema})]
    def post( self, t
            , _meta=None, _schema=None):
        """
        Creates new task instance.
        Example JSON:
            {
                "_meta" : { "time": <timestamp>, "host" : <localhost> },
                "typeLabel" : <task-class-name>,
                "config" : <arbitrary-config>,
                "processes" : { <str> : None|<int>|(<int>, <int>) }
                ["depGraph" : <networkx-bz2-compressed-base64-encoded>, ]
            }
        The `typeLabel` reflects the task class defined by user code.
        Upon successful task creation, returns `201 (CREATED)`. May return
        `409 (CONFLICT)` if `taskLabel` from query string is not unique.
        """
        resp = { 'created' : False }
        L, S = logging.getLogger(__name__), db.session
        ct = _meta['time'] if _meta else None
        t = _schema.load( t, session=S )
        # We require task label to be unique, so look up for existing one first:
        #t = S.query(models.Task).filter_by( name=name ).first()
        state = sqlalchemy.inspect(t)
        # XXX
        #print ('Transient: %s, Pending %s, Detached: %s, Persistent: %s' % (
        #        state.transient, state.pending, state.detached, state.persistent))
        L.debug(f'POST: taskName={t.name} from {flask.request.remote_addr}')
        with S.no_autoflush:
            if S.query(models.Task).filter_by( name=t.name ).first() is not None:
                resp['errors'] = [{ 'reason' : 'Task name is not unique.'
                                  , 'details' : schemata.taskSchema.dump(t) }]
                if not state.transient:
                    resp['errors'].append({'reason' : 'Deserialized task'
                        ' object is not transient.'})
                return resp, 409  # conflict
                # see: https://stackoverflow.com/questions/3825990/http-response-code-for-post-when-resource-already-exists
        # Check that task has at least one process defined within (empty tasks
        # are useless).
        if not t.processes:
            resp['errors'] = [{ 'reason' : 'Refuse to create task instance in DB.'
                              , 'details' : ['Task with no "processes".'] }]
            return resp, 400
        if _meta:
            t.submitted = _meta['time']
            t.hostname = _meta['host']
        t.submHostIP = flask.request.remote_addr
        S.add(t)
        S.commit()
        resp['created'] = True
        return resp, 201  # created

    def get(self, name=None):
        L, S = logging.getLogger(__name__), db.session
        L.debug(f'GET: taskName={name} from {flask.request.remote_addr}')
        if name:
            t = S.query(models.Task).filter_by(name=name).one_or_none()
            if t is None:
                return {'error': f'No task named {name} exists.'}, 404
            return schemata.taskSchema.dump(t)
        q = S.query(models.Task)
        # Otherwise, perform more complex query, if needed
        filterByTags=flask.request.args.getlist('tag')
        if filterByTags:
            q = q.filter(models.Task.tags.any(models.Tag.name.in_(filterByTags)))
        # TODO: submission/finished/whatever dates
        ts = q.all()
        return schemata.tasksSchema.dump(ts)

    def delete(self, name=None):
        """
        Perform deletion of particular task or all the task indexed in table.
        """
        L, S = logging.getLogger(__name__), db.session
        L.debug(f'DELETE: taskName={name} from {flask.request.remote_addr}')
        if name is None:
            return { 'error' : 'By security reasons, batch deletion of task '
                               'is forbidden.'
                    }, 403
        else:
            t = S.query(models.Task).filter_by(name=name).one()
            S.delete(t)
            S.commit()
            return { 'deleted' : 1 }, 200
