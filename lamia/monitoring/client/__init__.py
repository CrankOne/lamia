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
RESTful API. This module defines factory constructor for API of different
versions.
"""

import os
import urllib.parse, socket, logging
from contextlib import closing

def get_api_description_from_path( path ):
    if path:
        apiPath = path
        apiVer = [ptok for ptok in path.split('/') if ptok][-1]
    else:
        apiPath = '/api/v0/'
        apiVer = 'v0'
    return apiVer, apiPath

def instantiate_client_API( apiVer, apiPath ):
    if apiVer.startswith('v0'):
        from .api0 import LamiaMonitoringAPI
        return LamiaMonitoringAPI( apiPath )
    else:
        raise RuntimeError( 'Unknown client API version: "%s".'%apiVer )

def setup_monitoring_on_dest( monitoringAddr
                            , tags=None, comment=None
                            , username=None, email=None ):
    """
    Returns instantiated API instance if host is available or `None' otherwise.
    """
    L = logging.getLogger(__name__)
    if not monitoringAddr:
        L.info( "No Lamia monitoring host URI has been provided." )
        return None
    # Check if monitoring host is available by attempting to open index
    # page.
    try:
        p = urllib.parse.urlparse( monitoringAddr )
        with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
            sock.settimeout(2)
            ec = sock.connect_ex((p.hostname, p.port))
            if 0 != ec:
                L.error( 'Destination "%s" (hostname=%s, port=%d) is not'
                        ' available: "%s"'%(
                    p.netloc, p.hostname, p.port, os.strerror(ec)) )
                return None
        apiVer, apiPath = get_api_description_from_path(p.path)
        L.info( 'Assuming API of version {apiVer} on host {hostname} with port'
            ' {port} by addr {apiPath}.'.format( hostname=p.hostname
                                               , port=p.port if p.port else '80'
                                               , apiVer=apiVer
                                               , apiPath=apiPath ) )
        api = instantiate_client_API( apiVer, apiPath )
        api.set_host( p.hostname, p.port )
        api.taskPayload['tags'] = tags
        api.taskPayload['comment'] = comment
        api.taskPayload['username'] = username
        api.taskPayload['emailNotify'] = email
    except Exception as e:
        L.warning( 'Failed to communicate with monitoring server "%s"'
                ' due to a runtime error:'%monitoringAddr )
        L.exception( e )
        L.warning( 'Continuing without monitoring support due to previous error.' )
        return None
    return api
