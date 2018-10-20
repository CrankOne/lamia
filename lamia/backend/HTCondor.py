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
The rotuines for task submission on HTCondor clusters.

Since official Python bindings for HTCondor is quite rudimentary thing compared
to its shell toolchain, the purpose of this module is only to be a draft for
possible future elaboration...
"""

gPySubConfigs = {
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

    This way does not support dependency management making its practical
    meaning neglegible. Kept for possible future usage.
    """
    def backend_type():
        return 'HTCondor'

    def __init__(self, config):
        L = logging.getLogger(__name__)
        super().__init__(config)
        if 'scheddAd' in self.cfg:
            self._schedd = htcondor.Schedd()
            L.info( 'Instantiated default schedd handler: %s'%str(self._schedd) )
        else:
            self._schedd = htcondor.Schedd(self.cfg['scheddAd'])
            L.info( 'Instantiated schedd handler: %s with classAd'
                    ' retrieved from config.'%str(self._schedd) )

    def submit( self, jobName
                    , cmd=None
                    , stdout=None, stderr=None
                    , timeout=30
                    , backendArguments={}
                    , popenKwargs={} ):
        """
        Submits the job to processing using HTCondor Python bindings for
        ClassAds (no interim submission files).
        """
        L = logging.getLogger(__name__)
        assert(cmd)
        if type(cmd) is str:
            cmd = [cmd]
        if (type(cmd) is not list):
            raise TypeError( "First argument is expected to be a list' \
                            ' not a %s"%type(cmd).__name__ )
        classAd = copy.deepcopy(self.cfg['classAds.bsub'])
        classAd['cmd'] = cmd[0]
        if len(cmd) > 1:
            classAd['arguments'] = ' '.join(cmd[1:])
        return self._schedd.submit(classAd), None
        # OR:
        #sub = htcondor.Submit(classAd)
        #with self._schedd.transaction() as txn:
        #    clusterID = sub.queue(txn)
        #return clusterID, None

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
