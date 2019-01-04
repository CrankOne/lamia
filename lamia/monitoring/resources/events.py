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
"""

import flask_restful
import lamia.monitoring.orm as models
from lamia.monitoring.resources import validate_input
import flask, logging, json, schema
import lamia.monitoring.app
import lamia.monitoring.schemata as schemata

class Events(flask_restful.Resource):
    method_decorators = [validate_input(schemata.eventSchema)]
    def post(self, vd):
        resp = { 'valid' : False
               , 'taskID' : None
               , 'redundant' : False
               , 'considered' : False }
        L = logging.getLogger(__name__)
        S = lamia.monitoring.app.db.session
        # Look for task label
        if type( vd['from'] ) is str:
            task = S.query(models.BatchTask).filter_by(label=vd['from'] ).first()
        else:
            task = S.query(models.BatchTask).filter_by(label=vd['from'][0] ).first()
        if not task:
            resp['taskID'] = None
            resp['considered'] = False
            return resp, 404  # Well, no task found...
        resp['taskID'] = task.id
        if type( vd['from'] ) in (list, tuple):
            # Process within the array
            arr = S.query(models.ProcArray).filter_by( task_id=task.id
                                                     , name=vd['from'][1] ).first()
            if not arr:
                resp['arrayID'] = None
                L.error( 'Unable to locate array named "%s" within (existing)'
                        ' task "%s".', vd['from'][1], vd['from'][0] )
                return resp, 404
            resp['arrayID'] = arr.id
            # Find process entry within the array (create, if it doesn't exist)
            p = S.query(models.ArrayProcess).filter_by( array_id=arr.id
                                                       , job_num=vd['from'][2] ).first()
            if not p:
                p = models.ArrayProcess( job_num=vd['from'][2] )
                S.add(p)
                resp['processCreated'] = True
                arr.processes.append(p)
            else:
                resp['processCreated'] = False
        else:
            # Standalone process within the task
            p = S.query(models.StandaloneProcess).filter_by( task_id=task.id
                                                           , name=vd['from'] ).first()
            if not p:
                p = models.StandaloneProcess(name=vd['from'])
                task.jobs.append(p)
                S.add(p)
                resp['processCreated'] = True
                arr.processes.append(p)
            else:
                resp['processCreated'] = False
        # Create new event, associate with task and commit to DB
        eve = models.new_remote_proc_event(vd)
        p.events.append(eve)
        S.add(p)
        S.commit()
        resp['considered'] = True
        resp['eventID'] = eve.id
        #L.debug('Considered event of type ... from host ...')
        return resp, 201

