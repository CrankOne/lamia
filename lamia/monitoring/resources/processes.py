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

import logging
import flask_restful
import flask

from sqlalchemy.orm import with_polymorphic
from lamia.monitoring.orm import db

import lamia.monitoring.app
import lamia.monitoring.orm as models
import lamia.monitoring.schemata as schemata

class Processes(flask_restful.Resource):
    """
    Processes are immutable.
    """
    #method_decorators = [validate_input({'GET': schemata.processSchema})]
    def get( self, taskName, processName, _meta=None ):
        """
        GET returns a description of the particular process. For reference see:
            * polymorhpic loading of inherited classes in SQLA:
                https://docs.sqlalchemy.org/en/13/orm/inheritance_loading.html
            * filtering by presence of certain events:
                https://stackoverflow.com/questions/40524749/sqlalchemy-query-filter-on-child-attribute
        Supported additional query args:
            `hasEventsOfClass=<CLASSNAME>' -- if process name is set to `@all',
            filters processes by presense of certain event (STARTED or FINISHED
            may be useful).
        """
        L, S = logging.getLogger(__name__), db.session
        Ps = with_polymorphic( models.Process, [models.Array,] )
        #
        isArray = flask.request.args.get('isArray', False)
        hasEventsOfClass = flask.request.args.get('hasEventsOfClass', None)
        #
        if '@all' != processName:
            j = S.query(Ps).filter_by( taskID=taskName, name=processName ).one()
            #print('xxx', j.lastEventClass)  # XXX
            return schemata.polyProcessSchema.dump(j), 200
        # Build up a query
        q = S.query(Ps)
        if hasEventsOfClass:
             q = q.join(models.Event, models.Process.events).filter(
                     models.Event.eventClass == hasEventsOfClass)
        return [ schemata.polyProcessSchema.dump(e) for e in q.all() ], 200
        #return schemata.arraySchema.dump(j)


