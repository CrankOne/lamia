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

class Arrays(flask_restful.Resource):

    method_decorators = [validate_input(schemata.arraySchema)]

    def post(self, vd, taskLabel, arrayName=None):
        if not arrayName:
            raise ValueError('No "arrayName" provided.')
        L, S = logging.getLogger(__name__), lamia.monitoring.app.db.session
        cTime, cHost = vd['!meta']['time'], vd['!meta']['host']
        # We require task label to be unique, so look up for existing one first:
        t = S.query(models.BatchTask).filter_by( label=taskLabel ).one()
        a = models.ProcArray( submitted=cTime, host=cHost
                            , nJobs=vd['nJobs']
                            , name=arrayName
                            , fTolerance=vd['tolerance'] )
        t.arrays.append(a)
        S.add(a)
        S.commit()
        L.info( "{host}:{time} :: Created array, id={id_}".format(
                host=cHost, time=unicode(cTime), id_=a.id ) )
        return {'created' : True}, 201

    #def get(self, taskLabel, name=None):
    #    pass


