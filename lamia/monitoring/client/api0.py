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
import logging
import functools, io, base64, pickle, bz2, json, networkx, socket, time

class LamiaMonitoringAPI(object):
    """
    Client-side implementation of API of version 0.
    """

    def __init__(self, path):
        L = logging.getLogger(__name__)
        self._path = path
        # This properties will be sent as task payload
        self.taskName = None
        self._taskPayload = {}
        L.debug( 'Monitoring client api of version 0 instantiated.' )

    @property
    def hostURL(self):
        return 'http://{hostname}:{port}{path}'.format( hostname=self._dest[0]
                                                       , port=self._dest[1]
                                                       , path=self._path )

    def set_host(self, hostname, port=None):
        """
        Called after particular API instantiated.
        """
        L = logging.getLogger(__name__)
        self._dest = (hostname, port if port else 80)
        self.payload = {}
        L.debug( f'Monitor host set to "{hostname}", port={port}.' )

    def set_task_name(self, taskName):
        """
        Has to be called by users code after API is instantiated, but before
        any communication. May raise `KeyError' if task with given `taskName'
        exists -- users code must treat this case carefully.
        """
        L = logging.getLogger(__name__)
        conn = http.client.HTTPConnection('%s:%d'%self._dest)
        taskPath = os.path.join( self._path, taskName )
        conn.request( "GET", taskPath )
        r = conn.getresponse()
        conn.close()
        L.debug(f'GET:{taskPath} returned: {r.status}')
        if 404 != r.status:
            raise KeyError( 'Task with name "%s" is already listed'
                    ' by monitoring service.'%(taskName) )
            # todo: add details: submission information, user, etc.,
            # brought by response
        self._taskName = taskName

    def __setitem__(self, label, value):
        """
        Call this method to set the supplementary task information: task
        configuration to store, the tags list, username, comment, notification
        e-mail address, etc.
        """
        if label not in set(('username', 'config', 'tags'
                           , 'emailNotify', 'comment')):
            L.warning(f'Refusing to set "{label}" property of task payload'
                ' monitoring message.')
            return False
        if label in ('username', 'emailNotify', 'comment'):
            assert type(value) is str
        elif 'tags' == label:
            assert  type(value) in (list, tuple)
            assert all( type(t) is str for t in value )
        elif 'config':
            assert type(value) in (str, dict, tuple, list)
        else:
            assert False
        self._taskPayload[label] = value
        return True

    def job_event_address(self, processName, arrayNum=None):
        """
        Returns destination address for events of certain process.
        """
        p = os.path.join(self.get_task_URI_base(), processName)
        if arrayNum is not None:
            p += '/event?arrayIndex=%s'%str(arrayNum)
        return p

    def get_task_URI_base(self, taskName=None):
        """
        Returns base task URI. If taskName kwarg is given, the rendered path
        is for task name provided, otherwise own task name is used.
        """
        if not taskName:
            assert(self._taskName)
            taskName = self._taskName
        return '{baseURL}/{taskName}'.format(baseURL=self.hostURL, taskName=taskName)

    def follow_task(self, js):
        """
        Recieves the `lamia.core.backend.interface.Submission' subclass
        instance to form and submit the POST request for the monitoring server.
        The POST request imposes new task information.
        """
        L = logging.getLogger(__name__)
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
        else:
            dgpckl = io.BytesIO()
            networkx.write_gpickle(js.depGraph, dgpckl)
            g = base64.b64encode(bz2.compress(dgpckl.getvalue())).decode()
        # request data dict, to be updated with "task payload" dict
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
        # Recursively traverse job deps, acquiring all the processes --
        # standalone and arrays
        def _collect_deps( ps, stack ):
            for j in ps if type(ps) in (tuple, list) else (ps,):
                jobID = (j.jobName, id(j))
                skip = jobID in stack
                L.debug( ('Skipping' if skip else 'Adding')
                        + ' job (' + str(j) 
                        + ') to the list of processes to be monitored: "'
                        + j.jobName
                        + f'":[nProcs={j.nProcs}, isImplicitArray={j.isImplicitArray})] '
                        + ( '<- ' if stack else '(no deps)' )
                        + ' <- '.join([jj[0] for jj in stack]) )
                if not skip:
                    if 1 != j.nProcs or j.isImplicitArray:
                        if j.jobName in [jj[0] for jj in stack]:
                            raise KeyError( j.jobName )  # duplicating job name found in dependencies
                        if not j.minSuccess:
                            rqData['processes'][j.jobName] = j.nProcs*j.nImplicitJobs
                        else:
                            rqData['processes'][j.jobName] = [ j.nProcs*j.nImplicitJobs
                                                             , j.minSuccess*j.nImplicitJobs ]
                    else:
                        rqData['processes'][j.jobName] = None
                _collect_deps( j.dependencies, [jobID] + stack )
        _collect_deps( js, [] )
        # update the request data with "task payload"
        rqData.update(self._taskPayload)
        if 'config' in rqData and rqData['config']:
            if rqData['config']:
                rqData['config'] = base64.b64encode(bz2.compress(pickle.dumps(rqData['config']))).decode()
            #rqData['config'] = json.dumps(rqData['config'], default=str)
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
        # Send the request
        r = requests.post( self.get_task_URI_base()
                         , json=rqData
                         #, headers = {'Content-type': 'application/json', 'Accept': 'text/plain'}
                         # ^^^ weirdly, the `requests' does not always has
                         # JSON mimetype...
                         )
        # TODO: do something with the response data ...
        print( r.status_code, r.json() )

