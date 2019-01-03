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
Generic views defines the basic RESTful API

No HATEOAS currently implemented.
"""

import flask_restful
import lamia.monitoring.orm as models
import flask, logging, json, schema
import lamia.monitoring.app
from lamia.monitoring.resources import validate_input
import lamia.monitoring.schemata as schemata

class Tasks(flask_restful.Resource):
    method_decorators = [validate_input(schemata.taskSchema)]
    def post(self, vd):
        resp = { 'created' : False, 'valid' : True }
        L = logging.getLogger(__name__)
        S = lamia.monitoring.app.db.session
        ct = vd['!meta']['time']
        # We require task label to be unique, so look up for existing one first:
        t = S.query(models.BatchTask).filter_by(label=vd['label'] ).first()
        if t:
            return resp, 409  # conflict
            # see: https://stackoverflow.com/questions/3825990/http-response-code-for-post-when-resource-already-exists
        # Create task
        t = models.BatchTask( label=vd['label']
                            , submitted=ct
                            , dep_graph=vd.get('depGraph', None)
                            , task_type=vd.get('typeLabel', None) )
        if 'arrays' in vd:
            # fill task with arays
            arrs = []
            for arrNm, arrDscr in vd['arrays'].items():
                if type(arrDscr) is int:
                    arrs.append( models.ProcArray( submitted=ct
                                                 , name=arrNm
                                                 , nJobs=arrDscr ) )
                else:
                    # TODO: check that fTolerance < nJobs
                    arrs.append( models.ProcArray( submitted=ct
                                                 , name=arrNm
                                                 , fTolerance=arrDscr[0]
                                                 , nJobs=arrDscr[1] ) )
            t.arrays = arrs
            S.add_all(arrs)
        if 'jobs' in vd:
            t.jobs = [ models.StandaloneProcess(name=j, submitted=ct) for j in vd['jobs'] ]
            S.add_all(t.jobs)
        S.add(t)
        S.commit()
        resp['created'] = True
        return resp, 201  # created

    def get(self, taskLabel):
        if not taskLabel:
            return {'errors' : 'No task label given in request.'}, 400
        L = logging.getLogger(__name__)
        S = lamia.monitoring.app.db.session
        tt = S.query(models.BatchTask).filter_by(label=taskLabel).all()
        if not tt:
            return {'errors' : 'No task with label="{}" found.'.format(taskLabel)}, 404
        return [t.as_dict() for t in tt]
