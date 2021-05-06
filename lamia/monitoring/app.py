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
"""

import sys, os, yaml, logging.config
import flask, flask_restful, flask_cors

def create_app(cfg=None):
    """
    Flask application factory function. See:
        https://flask.palletsprojects.com/en/1.1.x/patterns/appfactories/
    """
    # Configure logging
    logging.config.dictConfig( cfg['logging'] )
    # Instantiate application
    app = flask.Flask(__name__)
    # Enable COR
    if cfg.get('enableCOR', False):
        # Add
        #   "Access-Control-Allow-Origin" : "*", 
        #   "Access-Control-Allow-Credentials" : true 
        # to request headers for cross-domain requests
        # see:
        #   https://stackoverflow.com/a/43547095
        #   https://stackoverflow.com/a/27423922
        #cors = flask_cors.CORS(app, allow_headers=['credentials'])
        cors = flask_cors.CORS(app, resources={r"/api/*": {"origins": "*"}}
                                  #, supports_credentials=True
                                  )
    api = flask_restful.Api(app)
    #app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/lamia-restful-test.sqlite3'
    # Configure application
    for k in cfg.keys():
        if k.isupper():
            app.config[k] = cfg[k]
    import lamia.monitoring.orm as models
    models.db.init_app(app)

    with app.app_context():
        models.db.create_all()
        from lamia.monitoring.resources.events import Events
        from lamia.monitoring.resources.processes import Processes
        from lamia.monitoring.resources.tasks import Tasks
        api.add_resource( Tasks
                , '/api/v0'
                , '/api/v0/<name>' )

        api.add_resource( Processes
                , '/api/v0/<taskName>/<processName>'
                )

        api.add_resource( Events
                , '/api/v0/<taskName>/<procName>/event'
                #, '/api/v0/<taskName>/<procName>/<int:procNumInArray>'  # xxx, query-encoded
                )
        #app.add_url_rule('/api/tasks',  view_func=Tasks.as_view('tasks'))
        #app.add_url_rule('/api/events', view_func=Events.as_view('events'))
        @app.route('/')
        def root_view():
            return 'Here be dragons.'
        return app

if "__main__" == __name__:
    inputFileName = sys.argv[1] if len(sys.argv) > 1 else 'assets/configs/rest-srv.yaml'
    with open(inputFileName) as f:
        cfg_ = yaml.load(f, Loader=yaml.FullLoader)
    cfgMode = os.environ.get('FLASK_ENV', 'PRODUCTION')
    cfg = cfg_[cfgMode]
    backendStr = cfg.get( 'backend', 'waitress' )
    if 'waitress' == backendStr:
        import waitress
        waitress.serve( create_app(cfg)
                      , host=cfg.get('host', '0.0.0.0')
                      , port=cfg.get('port', 8088) )

