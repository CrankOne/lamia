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
import sqlalchemy.orm
import lamia.monitoring.orm as models
import flask, logging, json
import lamia.monitoring.app
import lamia.monitoring.utils
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
        """
        Returns list of the active tasks. 
        """
        L, S = logging.getLogger(__name__), db.session
        L.debug(f'GET: taskName={name} from {flask.request.remote_addr}')
        if name:
            # query string is empty, perform standard query
            t = S.query(models.Task).filter_by(name=name).one_or_none()
            if t is None:
                return {'error': f'No task named {name} exists.'}, 404
            return schemata.taskSchema.dump(t)
        qp = {}
        if flask.request.args:
            rqa = flask.request.args.to_dict()
            s = schemata.TasksQuerySchema()
            errors = s.validate(rqa)
            if errors:
                return {'errors': errors}, 400
            qp = s.load(rqa)  # ? was flask.request.args
        q = S.query(models.Task)
        if 'tags' in qp and qp['tags']:
            L.debug('Filter task by tags: ' + ','.join(qp['tags']))
            # Works as OR-condition for multiple tags
            #q = q.filter(models.Task.tags.any(models.Tag.name.in_(qp['tags'])))
            # AND condition for tags
            for t in qp['tags']:
                q = q.filter(models.Task.tags.any(models.Tag.name == t))
        if 'fields' in qp:
            # TODO: `processes' and `tags' must be treated in different way
            # (relationships)
            if 'tags' in qp:
                q = q.options( sqlalchemy.orm.joinedload('tags').load_only('name') )
            if 'processes' in qp:
                #q = q.options()
                pass
            q = q.options(sqlalchemy.orm.load_only(*[f for f in qp['fields'] if f not in ['tags', 'processes'] ]))
        q, nTotal = lamia.monitoring.utils.apply_pagination(q, qp, models.Task)
        # Otherwise, perform more complex query, if needed
        # TODO: submission/finished/whatever dates
        s = schemata.TaskSchema(many=True, only=None if 'fields' not in qp else qp['fields'])
        return {'entries': s.dump(q.all()), 'total': nTotal}

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

