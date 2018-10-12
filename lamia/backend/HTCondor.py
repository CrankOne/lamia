import logging, os, shlex, copy, sys, subprocess #, htcondor
import lamia.core.filesystem
import lamia.core.templates
import lamia.backend.interface


"""
The rotuines for task submission on HTCondor clusters steered by BASH script.
"""

gSubConfigs = {'output'                  : 'output/HTCondor.out',
               'error'                   : 'error/HTCondor.err',
               'log'                     : 'log/HTCondor.log',
               'should_transfer_files'   : 'YES',
               'when_to_transfer_output' : 'ON_EXIT'
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
        L.debug("\n")
        L.debug("   Started to build file.sub")
        f.write("executable = {0}\n".format(cmd[0]))
        L.debug("executable = %s", cmd[0])
        if not 'output':
            gSubConfigs.update({'output' : stdout}) 
        if not 'error':
            gSubConfigs.update({'error'  : stderr})
        for k, v in gSubConfigs.items():
            f.write("{0} = {1}\n".format(k, v))
            L.debug("%s = %s"%(k, v))
# TODO: to understand what is queue        
        f.write("queue 1\n")
        L.debug("queue 1")
        f.close()
        L.debug("   file.sub was built\n")
        
        #forming the command line
        cmd_ = ['condor_submit', 'file.sub']
        L.debug("Command words are %s"%cmd_)
        #submitting the job
# TODO: to form actual stdout and stderr        
        pkw = copy.deepcopy({ 'stdout' : subprocess.PIPE
                            , 'stderr' : subprocess.PIPE
                            , 'universal_newlines' : True })
        pkw.update(popenKwargs)
        L.debug("Popen arguments are %s"%pkw)
        submJob = subprocess.Popen(cmd_, **pkw)
        #message = subprocess.check_output(cmd_)
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
