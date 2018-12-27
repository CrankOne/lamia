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

Code below constructs a primitive server.
"""
import logging, json, schema
import lamia.monitoring.schemata as schemata
import flask
from flask_sqlalchemy import SQLAlchemy

app = flask.Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/some.sqlite3'
db = SQLAlchemy(app)

import lamia.monitoring.orm as models
db.create_all()

@app.route('/')
def root_view():
    return 'Here be dragons.'

@app.route( '/api/event/proc'
          , methods=['POST'])
def proc_event():
    """
    This view will update the information about running process. It expects
    the request to bring information about task/array/process to which this
    task is related to in field `from'. Variants:
        <taskLabel:str>
        ^^^ for a single process within a task
        [ <taskLabel:str>, <arrayLabel:str>, <procNo:int> ]
        ^^^ for a process within an array within a task
    Additionally, the `payload' and `completion' fields might be supplied. The
    `payload' must be an object, it will be serialized to JSON and stored as an
    event. The `completion' might be either an int in range 0..100 indicating
    completeion percentage, or a pair of values (number of considered entities
    and number of overall entities).

    The `rc' field that must be an integer must accompany only the `term' type
    of events indicating the result of meaningful computation process exit
    code (0 is ok, !=0 is failure).

    Returned values:
        `considered:bool' whether or not this beat was taken into account; can
    be used as indication of the overall success.
        `valid:bool' whether the request passed the validation.
        `taskID:int' id of the task within the database, or null if task is not
    found.
        `redundant:bool' might be used by the client to decide whether the task
    has to be resumed or terminated in cases of there are redundant jobs pool.

    TODO: do we really need the `payload' here?
    """
    resp = { 'valid' : False
           , 'taskID' : None
           , 'redundant' : False
           , 'considered' : False }
    L = logging.getLogger(__name__)
    hrtbtData = flask.request.get_json()
    # ____/ Schema \____
    try:
        vd = schemata.gEventSchema.validate(hrtbtData)
    except schema.SchemaError as e:
        resp['valid'] = False
        L.exception( e )
        return flask.jsonify( resp )
    resp['valid'] = True
    # ----\ Schema /----
    S = db.session
    # Look for task label
    if type( vd['from'] ) is str:
        task = S.query(models.BatchTask).filter_by(label=vd['from'] ).first()
    else:
        task = S.query(models.BatchTask).filter_by(label=vd['from'][0] ).first()
    if not task:
        resp['taskID'] = None
        resp['considered'] = False
        return flask.jsonify( resp ), 404  # Well, no task found...
    resp['taskID'] = task.id
    if type( vd['from'] ) in (list, tuple):
        # Process within the array
        arr = S.query(models.ProcArray).filter_by( task_id=task.id
                                                 , name=vd['from'][1] ).first()
        if not arr:
            resp['arrayID'] = None
            L.error( 'Unable to locate array named "%s" within (existing)'
                    ' task "%s".', vd['from'][1], vd['from'][0] )
            return flask.jsonify( resp ), 404
        resp['arrayID'] = arr.id
        # Find process entry within the array (create, if it doesn't exist)
        p = S.query(models.RemoteProcess).filter_by( array_id=arr.id
                                                   , job_num=vd['from'][2] ).first()
        if not p:
            p = models.RemoteProcess( job_num=vd['from'][2] )
            S.add(p)
            resp['processCreated'] = True
            arr.processes.append(p)
        else:
            resp['processCreated'] = False
    else:
        # Standalone process within the task
        p = S.query(models.RemoteProcess).filter_by( task_id=task.id
                                                   , name=vd['from'] ).first()
    # Create new event, associate with task and commit to DB
    eve = models.RemProcEvent( timestamp=vd['meta']['time']
                             , ev_type=vd['type'] )
    p.events.append(eve)
    S.add(p)
    S.commit()
    resp['considered'] = True
    resp['eventID'] = eve.id
    #L.debug('Considered event of type ... from host ...')
    return flask.jsonify( resp )

@app.route( '/api/task/new'
          , methods=['PUT'])
def new_task():
    """
    Created new task.
    Optional field `depGraph' may bring networkx graph instance reflecting the
    dependencies within the task. The `depgraph' shall contain base64-encoded
    BZ2-compressed pickled representation of networkx DiGraph() instance.
    Mandatory `config' object will be stored as is for further usage.
    Optional `jobs' and `arrays' fields will cause creation of corresponding
    objects.
    """
    resp = { 'created' : False, 'valid' : True }
    L = logging.getLogger(__name__)
    S = db.session
    newTaskData = flask.request.get_json()
    try:
        vd = schemata.gTaskSchema.validate(newTaskData)
    except schema.SchemaError as e:
        resp['valid'] = False
        L.exception( e )
        return flask.jsonify( resp ), 400  # bad request
    # We require task label to be unique, so look up for existing one first:
    t = S.query(models.BatchTask).filter_by(label=vd['label'] ).first()
    if t:
        resp['taskID'] = t.id
        return flask.jsonify( resp ), 409  # conflict
        # see: https://stackoverflow.com/questions/3825990/http-response-code-for-post-when-resource-already-exists
    # Create task
    t = models.BatchTask( label=vd['label']
                        , submitted=vd['meta']['time']
                        , dep_graph=vd.get('depGraph', None)
                        , task_type=vd.get('typeLabel', None) )
    if 'arrays' in vd:
        # fill task with arays
        arrs = []
        for arrNm, arrDscr in vd['arrays'].items():
            if type(arrDscr) is int:
                arrs.append( models.ProcArray( submitted=vd['meta']['time']
                                             , name=arrNm
                                             , nJobs=arrDscr ) )
            else:
                # TODO: check that fTolerance < nJobs
                arrs.append( models.ProcArray( submitted=vd['meta']['time']
                                             , name=arrNm
                                             , fTolerance=arrDscr[0]
                                             , nJobs=arrDscr[1] ) )
        t.arrays = arrs
        S.add_all(arrs)
    if 'jobs' in vd:
        t.jobs = [ models.RemoteProcess(name=j, submitted=vd['meta']['time']) for j in vd['jobs'] ]
        S.add_all(t.jobs)
    S.add(t)
    S.commit()
    resp['created'] = True
    resp['taskID'] = t.id
    return flask.jsonify( resp ), 201  # created

@app.route( '/api/search'
          , methods=['POST']):
    pass

