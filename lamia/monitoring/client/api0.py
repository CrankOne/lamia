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
RESTful API. This module defines alpha API.
"""

import os.path
import urllib.request
import http.client
import requests
import functools, io, base64, pickle, bz2, json, networkx, socket, time

class LamiaMonitoringAPI(object):
    """
    Client-side implementation of API of version 0.
    """

    def __init__(self, path):
        self._path = path
        self._taskName = None
        self.taskPayload = {}

    @property
    def hostURL(self):
        return 'http://{hostname}:{port}{path}'.format( hostname=self._dest[0]
                                                       , port=self._dest[1]
                                                       , path=self._path )

    def set_host(self, hostname, port=None):
        """
        Called after particular API instantiated.
        """
        self._dest = (hostname, port if port else 80)
        self.payload = {}

    def set_task_name(self, taskName):
        """
        Has to be called by users code after API is instantiated, but before
        any communication. May raise `KeyError' if task with given `taskName'
        exists -- users code must treat this case carefully.
        """
        conn = http.client.HTTPConnection('%s:%d'%self._dest)
        conn.request( "GET", os.path.join( self._path, taskName ) )
        r = conn.getresponse()
        conn.close()
        if 404 != r.status:
            raise KeyError( 'Task with name "%s" is already listed'
                    ' by monitoring service.'%(taskName) )
            # todo: add details: submission information, user, etc.,
            # brought by response
        self._taskName = taskName

    def set_configs(self, *args, **kwargs):
        # TODO
        pass

    def job_event_address(self, processName, arrayNum=None):
        """
        Returns destination address for events of certain process.
        """
        p = os.path.join(self.get_task_URI_base(), processName)
        if arrayNum is not None:
            p += '?arrayIndex=%s'%str(arrayNum)
        return p

    def get_task_URI_base(self, taskName=None):
        if not taskName:
            taskName = self._taskName
        return '{baseURL}/{taskName}'.format(baseURL=self.hostURL, taskName=taskName)

    def follow_task(self, js):
        """
        Recieves the `lamia.core.backend.interface.Submission' subclass
        instance to form the POST request for the monitoring server imposing
        particular new task information.
        """
        g = None
        if type(js) in (list, tuple) or js.dependencies:
            # build the deps graph
            def _dep_convolution(acc, b):
                acc.update(b.depGraph)
                return acc
            g = functools.reduce( _dep_convolution, [networkx.DiGraph()] + list(js) )
            dgpckl = io.BytesIO()
            networkx.write_gpickle(g, dgpckl)
            g = base64.b64encode(bz2.compress(dgpckl.getvalue())).decode()
        rqData = { '_meta' : { 'host' : socket.gethostname()
                             , 'time' : str(time.time()) }
                 # Set by caller
                 #, 'config' : (from payload)
                 # Derived from `Submission' subclass instance
                 , 'depGraph' : g
                 , 'processes' : {}
                 # Set by user from command line/external interface
                 #, 'tags' : (from payload)
                 #, 'emailNotify' : (from payload)
                 #, 'username' : (from payload)
                 #, 'comment' : (from payload)
        }
        # Reqursively traverse job deps, acquiring all the processes --
        # standalone and arrays
        def _collect_deps( ps ):
            for j in ps if type(ps) in (tuple, list) else (ps,):
                if 1 != j.nProcs or j.isImplicitArray:
                    assert( j.jobName not in rqData['processes'] )
                    if not j.minSuccess:
                        rqData['processes'][j.jobName] = j.nProcs*j.nImplicitJobs
                    else:
                        rqData['processes'][j.jobName] = [ j.nProcs*j.nImplicitJobs
                                                         , j.minSuccess*j.nImplicitJobs ]
                else:
                    rqData['processes'][j.jobName] = None
                _collect_deps( j.dependencies )
        _collect_deps( js )
        rqData.update(self.taskPayload)
        #
        #print( 'data to sent:', json.dumps(rqData, sort_keys=True, indent=2) )  # XXX
        #print('xxx', self.get_task_URI_base())
        #
        #req = urllib.request.Request(self.get_task_URI_base())
        #req.add_header('Content-Type', 'application/json; charset=utf-8')
        #jsondata = json.dumps(rqData, default=str)
        #jsondataasbytes = jsondata.encode('utf-8')  # needs to be bytes
        #req.add_header('Content-Length', len(jsondataasbytes))
        #response = urllib.request.urlopen(req, jsondataasbytes)
        #print(response)
        r = requests.post( self.get_task_URI_base()
                         , json=json.dumps(rqData, default=str)
                         )
        print( r.status_code, r.json() )

