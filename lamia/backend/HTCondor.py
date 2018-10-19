# -*- coding: utf-8 -*-
# Copyright (c) 2018 Konstantin Sharko <gecko09@outlook.com>,
#                    Renat R. Dusaev <crank@qcrypt.org>
# Author: Konstantin Sharko <gecko09@outlook.com>,
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

import logging, os, copy, subprocess, htcondor
import lamia.backend.interface


"""
The rotuines for task submission on HTCondor clusters steered by BASH script.
"""

gPySubConfigs = {
    'cmd' : '',
    'arguments' : '',
    'output' : 'output/HTCondor.out',
    'error' : 'error/HTCondor.err',
    'userLog' : 'log/HTCondor.log',
    'ShouldTransferFiles' : 'YES',
    'when_to_transfer_output' : 'ON_EXIT'
}

class HTCondorPyBackend(lamia.backend.interface.BatchBackend):
    """
    The batch-processing back-end implementation for HTCondor.
    Relies on third-party Pythonic bindings for HTCondor facility (module
    `htcondor')
    """
    def backend_type():
        return 'HTCondor'

    def __init__(self, config):
        super().__init__(config)

    def submit(self, jobName,
                     cmd=None,
                     stdout=None,
                     stderr=None,
                     timeout=30,
                     backendArguments={},
                     popenKwargs={} ):
        """
        Submit the job to HTCondor
        Will forward `cmd' as a string within the `subprocess.Popen'
        """
        L = logging.getLogger(__name__)
        # building ClassAd
        if (type(cmd) is not list):
            raise TypeError( "First argument is expected to be a list' \
                            ' not a %s"%type(cmd) )
        if stdout:
            gPySubConfigs.update({'output' : stdout})
        if stderr:
            gPySubConfigs.update({'error' : stderr})
        gPySubConfigs['cmd'] = cmd[0]
        gPySubConfigs['arguments'] = ' '.join(cmd[1:])
        #submitting the job
        schedd = htcondor.Schedd()
        schedd.submit(gPySubConfigs)
        L.debug("Command is %s"%(' '.join(cmd)))
        # TODO: to take configs from the config directory, not from local
        # TODO: to build the properties to return
        return {'jID':'1', 'queue':'1'}

    def dump_logs_for(self, jID, popenKwargs={}):
        pass

    def get_status(self, jID, popenKwargs={}):
        pass

    def kill_job(self, jID, popenKwargs={}):
        pass

    def list_jobs(self, timeout=30, backendArguments=[], popenKwargs={}):
        pass

    def wait_for_job(self, jID, popenKwargs={}):
        """
        See:
            https://www-auth.cs.wisc.edu/lists/htcondor-users/2014-January/msg00152.shtml
            https://github.com/DyogenIBENS/CondorViaPython/blob/master/condor.py#L115
        """
        pass
