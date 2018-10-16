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

import logging, os, copy, subprocess, htcondor
import lamia.core.filesystem
import lamia.core.templates
import lamia.backend.interface


"""
The rotuines for task submission on HTCondor clusters steered by BASH script.
"""

gSubConfigs = {'output'                   : 'output/HTCondor.out',
               'error'                    : 'error/HTCondor.err',
               'log'                      : 'log/HTCondor.log',
               'should_transfer_files'    : 'YES',
               'when_to_transfer_output'  : 'ON_EXIT'
              }

gPySubConfigs = {'cmd'                    : '',
                 'arguments'              : '',
                 'output'                 : 'output/HTCondor.out',
                 'error'                  : 'error/HTCondor.err',
                 'userLog'                : 'log/HTCondor.log',
                 'ShouldTransferFiles'    : 'YES',
                 'when_to_transfer_output':'ON_EXIT'
                }

class HTCondorBackend(lamia.backend.interface.BatchBackend):
    """
TODO: Short description

TODO: Detailed description
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
        
        # creating .sub file
        f = open('file.sub', 'w+')
        if (type(cmd) is not list):
            raise TypeError( "First argument is expected to be a list' \
                            ' not a %s"%type(cmd) )
        L.debug("Started to build file.sub")
        f.write("executable = {0}\n".format(cmd[0]))
        f.write("arguments = ")
        for i in range(len(cmd))[1:]:
            f.write("{0} ".format(cmd[i]))
        f.write("\n")
        if stdout:
            gSubConfigs.update({'output' : stdout}) 
        if stderr:
            gSubConfigs.update({'error'  : stderr})
        for k, v in gSubConfigs.items():
            f.write("{0} = {1}\n".format(k, v))
        f.write("queue 1\n")
        f.close()
        L.debug("file.sub was built\n")
        
        #forming the command line
        cmd_ = ['condor_submit', 'file.sub']
        L.debug("Command for submittion is %s"%(" ".join(cmd_)))
        #submitting the job
        pkw = copy.deepcopy({ 'stdout' : subprocess.PIPE
                            , 'stderr' : subprocess.PIPE
                            , 'universal_newlines' : True })
        pkw.update(popenKwargs)
        L.debug("Popen arguments are %s"%pkw)
        submJob = subprocess.Popen(cmd_, **pkw)
        #message = subprocess.check_output(cmd_)
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
        pass



class HTCondorPyBackend(lamia.backend.interface.BatchBackend):
    """
TODO: Short description

TODO: Detailed description
    """

    def backend_type():
        return 'HTCondorPy'


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
        pass
