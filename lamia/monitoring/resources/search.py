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
Generic views defines the basic RESTful API.

No HATEOAS currently implemented.
"""

from lamia.monitoring.views import json_input

import lamia.monitoring.schemata

#   create task
#   event
#   look-up for any object available
#   query for set of objects

#basicAPI = flask.Blueprint( 'basic-api', __name__ )


#@basicAPI.route('/events', methods=['POST'])
#@json_input(lamia.monitoring.schemata.gEventSchema)


#@basicAPI.route( '/task/new', methods=['PUT'])
#@json_input(lamia.monitoring.schemata.gTaskSchema)
#def new_task( vd ):
#
#@basicAPI.route( '/search', methods=['POST'])
#def search():
#    pass

