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

import logging, json, schema, flask, flask_sqlalchemy, flask_restful

app = flask.Flask(__name__)
api = flask_restful.Api(app)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/some.sqlite3'
db = flask_sqlalchemy.SQLAlchemy(app)
import lamia.monitoring.orm as models
db.create_all()

from lamia.monitoring.resources.events import Events
from lamia.monitoring.resources.tasks import Tasks
from lamia.monitoring.resources.arrays import Arrays
from lamia.monitoring.resources.jobs import Jobs

api.add_resource( Tasks, '/api/v0'
                       , '/api/v0/<taskLabel>')

api.add_resource(Arrays, '/api/v0/<taskLabel>/arrays'
                       , '/api/v0/<taskLabel>/arrays/<arrayName>')

api.add_resource(  Jobs, '/api/v0/<taskLabel>/jobs'
                       , '/api/v0/<taskLabel>/jobs/<jobName>'
                       , '/api/v0/<taskLabel>/arrays/<arrayName>/<jobNum>' )

api.add_resource(Events, '/api/v0/<taskLabel>/jobs/<jobName>/<eventID>'
                       , '/api/v0/<taskLabel>/arrays/<arrayName>/<jobNum>/<eventID>' )

#app.add_url_rule('/api/tasks',  view_func=Tasks.as_view('tasks'))
#app.add_url_rule('/api/events', view_func=Events.as_view('events'))

@app.route('/')
def root_view():
    return 'Here be dragons.'

