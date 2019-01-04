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
Here the search queries as a first-class objects must be implemented.

Due to the technical difficulties of expressing query requests in JSON format,
we postpone this implementation.

One may find a simple resource declaring some reentrant frequent querying
prototypes for immediate practical usage.
"""

from lamia.monitoring.views import json_input

import lamia.monitoring.schemata

import flask_restful
import lamia.monitoring.orm as models
import flask, logging, json, schema
import lamia.monitoring.app
from lamia.monitoring.resources import validate_input
import lamia.monitoring.schemata as schemata

def query_active_tasks():
    """
    Retrieves the tasks currently being active. A task considered active if
    at least one of its processes (jobs or array element) is active (i.e. have
    no termination event).
    """
    pass

def query_active_processes():
    """
    A process considered active if it does not have a termination event.
    """
    L = logging.getLogger(__name__)
    S = lamia.monitoring.app.db.session
    pcs = S.query( models.RemoteProcess, models.RemProcEvent ) \
            .filter( models.RemoteProcess.id == models.RemProcEvent.proc_id ) \
            .filter( models.RemProcEvent.type != 'termination_events' ).all()
    return pcs

class Search(flask_restful.Resource):
    method_decorators = [validate_input(schemata.searchSchema)]

    # TODO: shall create and cache query object
    #def post(self, vd):
    #    pass

    def get(self, queryID=None):
        pass
