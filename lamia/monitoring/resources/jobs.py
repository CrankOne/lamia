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
View defining jobs as a resource.

No HATEOAS currently implemented.
"""

import flask_restful
import lamia.monitoring.orm as models
import flask, logging, json, schema
import lamia.monitoring.app
from lamia.monitoring.resources import validate_input
import lamia.monitoring.schemata as schemata

# TODO: consider to move it
def new_remote_proc_event( vd ):
    if 'terminated' == vd['type']:
        return models.RemProcTerminated( timestamp=vd['!meta']['time']
                                       , ev_type=vd['type']
                                       , completion=vd.get('exitCode', None) )
    elif 'beat' == vd['type']:
        return models.RemProcBeatProgress( timestamp=vd['!meta']['time']
                                         , ev_type=vd['type']
                                         , completion=vd.get('exitCode', None) )
    else:
        return models.RemProcEvent( timestamp=vd['!meta']['time']
                                  , ev_type=vd['type'] )

class Jobs(flask_restful.Resource):

    method_decorators = [validate_input(schemata.procSchema)]

    def post( self, vd, taskLabel
            , jobName=None, arrayName=None, jobNum=None ):
        """
        Used to initialize writing of event chain describing certain remote
        process. Updates shall then be submitted within PUT request.
        """
        L, S = logging.getLogger(__name__), lamia.monitoring.app.db.session
        cTime, cHost = vd['!meta']['time'], vd['!meta']['host']
        # We require task label to be unique, so look up for existing one first:
        t = S.query(models.BatchTask).filter_by( label=taskLabel ).one()
        if jobName and arrayName:
            raise ValueError('Both "jobName" and "arrayName" parameters provided.')
        elif jobName:
            # Create single job history
            p = models.StandaloneProcess( submitted=cTime, host=cHost
                                        , name=jobName )
            p.task = t
            t.jobs.append(p)
        elif arrayName and jobNum:
            a = S.query(models.ProcArray).filter_by(name=name, task=t).one()
            # Create array job history
            p = models.ArrayProcess( name=arrayName, job_num=int(jobNum) )
            a.processes.append(p)
        else:
            raise ValueError('No job name identifier provided.')
        S.add(p)
        S.commit()
        if jobName:
            L.info( "{host}:{time} :: Created standalone job, id={id_}".format(
                host=cHost, time=str(cTime), id_=p.id ) )
        else:
            L.info( "{host}:{time} :: Created array job, id={id_}".format(
                host=cHost, time=str(cTime), id_=p.id ) )
        return {'created' : True}, 201


    def put( self, vd, taskLabel
           , jobName=None, arrayName=None, jobNum=None):
        """
        Expects process status updating events.
        """
        L, S = logging.getLogger(__name__), lamia.monitoring.app.db.session
        cTime, cHost = vd['!meta']['time'], vd['!meta']['host']
        # We require task label to be unique, so look up for existing one first:
        #t = S.query(models.BatchTask).filter_by( label=taskLabel ).one()
        if jobName and arrayName:
            raise ValueError('Both "jobName" and "arrayName" parameters provided.')
        elif jobName:
            p = S.query( models.StandaloneProcess ).join( models.BatchTask ) \
                    .filter( models.BatchTask.id == models.StandaloneProcess.task_id ) \
                    .filter( models.BatchTask.label == taskLabel ) \
                    .filter( models.StandaloneProcess.name == jobName ).one()
            eve = new_remote_proc_event( vd )
            p.events.append(eve)
            S.add(eve)
            S.commit()
            return {'created' : True}
        elif arrayName and jobNum:
            # models.ArrayProcess
            array
        else:
            raise ValueError('No job name identifier provided.')
        #S.add(p)
        #S.commit()
        #if jobName:
        #    L.info( "{host}:{time} :: Created standalone job, id={id_}".format(
        #        host=cHost, time=unicode(cTime), id_=p.id ) )
        #else:
        #    L.info( "{host}:{time} :: Created array job, id={id_}".format(
        #        host=cHost, time=unicode(cTime), id_=p.id ) )
        #return {'created' : True}, 201

