# -*- coding: utf-8 -*-
# Copyright (c) 2017 Renat R. Dusaev <crank@qcrypt.org>
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

import abc, os, logging, sys, copy, argparse, re
import lamia.core.configuration \
     , lamia.logging \
     , lamia.core.task

rxArg = re.compile(r'^(?P<key>\w+):(?P<backend>\w+)?=(?P<value>.*)$')

class BackendCommandError(RuntimeError):
    """
    An exception class bearing information about error happened during
    invokation of command sent to the back-end.
    We consider that error is happened if either the Popen() failed, or the
    shell command return code is non-zero. In both cases, user code must be
    notified.
    """
    def __init__(self, output={'stdout':None, 'stderr':None, 'rc':None}
                     , exception=None):
        self.output = output
        self.exception = exception
        message = "Batch back-end error occured."
        if self.exception:
            message += "An \"%s\" exception occured while subprocessing."%(str(exception))
        else:
            message += "See `output' property(-ies) associated."
        super().__init__(message)
    # TODO: repr() or str() or?..


class SubmissionFailure(BackendCommandError):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

class JListFailure(BackendCommandError):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)

#{
#    # An arbitrary expression to uniqely identify the current
#    # session
#    'sessionTag' : os.environ.get('TTAG', '%x'%int(datetime.datetime.now().timestamp())),
#    'taskName' : taskName,
#    # The pattern for log files path. All the self.cfg object will
#    # be used for formatting + the `logType'=(out|err) strings.
#    'jobStdout' : '/tmp/%(taskName)s.%(sessionTag)s.%(backendType)s.%(jobName)s.%(logType)s.txt'
#}

class BatchBackend(abc.ABC):
    """
    Defines basic properties system for every batch-processing backend.
    The few abstract method designed for job submission, its status retreival
    and interruption.
    The only demand for these method is compatibility of jID. It has be an
    instance of arbitrary type that must be returned by submit() and understood
    by kill.../wait.../get_status/.../etc. methods.
    """
    def __init__( self, config ):
        """
        Ctr accepts a config object of form sutable for
        lamia.core.configuration.Configuration instance.
        """
        L = logging.getLogger(__name__)
        self.cfg = lamia.core.configuration.Stack()
        self.cfg.push(lamia.core.configuration.Configuration(config))

    @property
    @abc.abstractmethod
    def backend_type(self):
        """
        Must return a string identifying this back-end (e.g.
        LSF/HTCondor/etc.)
        """
        pass

    @abc.abstractmethod
    def submit(self, jobName, nProcs=1
                   , cmd=None
                   , stdout=None, stderr=None
                   , timeout=30
                   , backendArguments={}
                   , popenKwargs={} ):
        """
        Shall submit job and, upon successful submission, return the "job
        submitted properties" object.
        * The `cmd' must be either a list of shell command arguments to submit,
        or the entire command, or None/'-' indicating that input from stdin
        has to be retrieved.
        * The `nProcs' denotes a set of homogeneous jobs. The back-end may or
        may not imply this term directly as "arrays", but it is esentially the
        same for most facilites.
        * The `backendArguments' is an optional parameters usually provided to
        submission command, steering the submission process itself. Here, they
        overrides what is given to ctr. Expected to be of `dict' type.
        * The `popenKwargs' is rarely used dictionary of arguments forwarded to
        Python's subprocess.Popen() ctr.
        Returns the two objects: a job ID and the dictionary of arbitrary
        properties that user code might found useful (but we do not demand it
        be of some certain form).
        * The `stdour'/`stderr' arguments will undergo the string interpolation
        prior the actual submission with backend-specific special placeholders
        substitution. The list of common interpolation variables are:
            - {jIndex} -- `%I' for LSF, `$(Process)' for HTCondor
            - {jID} -- `%J' for LSF, `$(Cluster).$(Process)' for HTCondor
        Note, that for `nProcs' != 1 your submission must provide at least one
        of this macros within stderr/stdout.
        """
        pass

    @abc.abstractmethod
    def get_status(self, jID, backendArguments={}, popenKwargs={}):
        """
        By given `jID' (of possibly arbitrary type), shall return "active job
        properties object".
        """
        pass

    @abc.abstractmethod
    def kill_job(self, jID, popenKwargs={}):
        """
        By given `jID' (of possibly arbitrary type), shall initiate job
        interruption process (possibly asynchroneous).
        """
        pass

    @abc.abstractmethod
    def wait_for_job( self, jID
                    , nAttempts=0
                    , intervalSecs=60
                    , backendArguments={}
                    , popenKwargs={}
                    , report=True ):
        """
        Will await for job of given `jID' to finish, periodically retrieving
        it's status.
        Despite user must avoid usage of such a silly procedure in favor of
        dependency management, this approach is still useful for some
        quick'n'dirty solutions, or for short-term blocking tasks.
        """
        pass

    @abc.abstractmethod
    def dump_logs_for( self, jID, popenKwargs={} ):
        """
        Returns stdout and stderr dumps (in order) of job by given ID. Some
        back-ends do not support separated dump for stdout and stderr, so both
        of them will be returned.
        """
        pass

    @abc.abstractmethod
    def list_jobs( self, timeout=30, popenKwargs={} ):
        """
        Retrieves a list of currently active (or recently done, if appliable)
        jobs. Returns a dictionary, indexed with jobID object.
        """
        pass

def instantiate_backend( name, config, *args, **kwargs ):
    """
    A virtual constructor for back-end instances: creates particular back-end
    instance based on its string name (cf. factory).
    """
    L = logging.getLogger()
    backEnds = {}
    if not BatchBackend.__subclasses__():
        raise RuntimeError( "No back-ends available." )
    for c in BatchBackend.__subclasses__():
        if c.backend_type() == name:
            return c(config, *args, **kwargs)
    raise LookupError("Unable to find batch back-end"
            " interface implementation \"%s\"."%name)

#
# Utility imperatives
####################

gCommonParameters = {
    'argument,A' : {
        'help' : "An argument to be forwarded"
            " to back-end command shell invokation. Must be avoided in mature"
            " code, but is still useful for the debug and development."
            " Expected to be given in form <key>[:<backend>]=<value>."
            " The <backend> parameter is optional and makes this "
            " specification to be only active for certain back-end.",
        'action' : "append",
        'dest' : 'backend_arguments'
    },
    'backend,B' : {
        'help' : "One of the batch back-ends available."
    },
    'backend_config' : {
        'help' : "Configuration file for the backend to be used."
    }
}

def backend_specific_args( given, backend ):
    L = logging.getLogger(__name__)
    submArgs={}
    for strPair in given or []:
        m = rxArg.match(strPair)
        if not m:
            raise ValueError('Unable to interpret submission argument' \
                    ' expression "%s".'%strPair )
        if 'backend' in m.groupdict().keys() \
        and backend != m.groupdict()['backend']:
            L.debug("Parameter `%s:%s=%s' is omitted (using %s)."%(
                    m.groupdict()['key'],
                    m.groupdict()['backend'],
                    m.groupdict()['value'],
                    backend ))
            continue
        submArgs[m.groupdict()['key']] = m.groupdict()['value']
    return submArgs


def available_backends():
    return [ c.backend_type() for c in BatchBackend.__subclasses__() ]


class BatchTask( lamia.core.task.Task
               , metaclass=lamia.core.task.TaskClass ):
    """
    General base class for batch-operating tasks.
    """
    __commonParameters = gCommonParameters

    @property
    def backend(self):
        if not hasattr(self, '_backendName') \
        or not hasattr(self, '_backendConfig'):
            raise AssertionError("Backend attributes are not initialized yet.")
        if not hasattr(self, '_backend'):
            self._backend = instantiate_backend( self._backendName
                                               , self._backendConfig )
        return self._backend

class BatchSubmittingTask( BatchTask
                         , metaclass=lamia.core.task.TaskClass ):
    """
    Implements job-submitting action, utilizing certain back-end.
    """
    __execParameters = {
        'result_format,f' : {
            'help' : "Sepcifies the form of message being printed back"
                " upon successfull job submission. Must be a python"
                " format() string consuming at least the {jID} variable"
                " (rest are backend-specific)."
        },
        'stdout_log,o' : {
            'help' : "Specifies a file where job's stdout has to be written."
        },
        'stderr_log,e' : {
            'help' : "Specifies a file where job's stdout has to be written."
        },
        'job_name,J' : {
            'help' : "A name of the job."
        },
        '@fwd' : {
            'nargs' : argparse.REMAINDER
        }
    }
    __defaults = {
        'result_format' : "jID={jID}"
    }

    def submit( self, fwd
              , jobName=None, nProcs=1
              , stdoutLog=None, stderrLog=None
              , backendArguments={} ):
        try:
            r = self.backend.submit( jobName, nProcs=nProcs
                                   , cmd=fwd
                                   , stdout=stdoutLog, stderr=stderrLog
                                   , backendArguments=backendArguments )
        except JListFailure as e:
            sys.stderr.write( 'Submission error occured: rc=%s\n'%e.output['rc'] )
            if not e.exception:
                L.error( '<submission command stdout>:\n' )
                L.error( e.output['stdout'].decode('ascii') )
                L.error( '<submission command stderr>:\n' )
                L.error( e.output['stderr'].decode('ascii') )
            else:
                L.exception( e.exception )
        return r

    def _main( self
             , fwd=[]
             , backend=None, backendConfig=None
             , stderrLog=None, stdoutLog=None
             , jobName=None
             , backendArguments={}
             , resultFormat='' ):
        L = logging.getLogger(__name__)
        self._backendName, self._backendConfig = backend, backendConfig
        if not fwd:
            self.argParser.error( 'Nothing to submit.' )
        if not jobName:
            self.argParser.error( 'Job name is not set.' )
        backendArguments = backend_specific_args( backendArguments, backend )
        r = self.submit( fwd, jobName=jobName
                       , stdoutLog=stdoutLog, stderrLog=stderrLog
                       , backendArguments=backendArguments )
        sys.stdout.write( resultFormat.format(**r) )
        return 0

class BatchListingTask( BatchTask
                      , metaclass=lamia.core.task.TaskClass ):
    __execParameters = {
        'result_format,f' : {
            'help' : "Sepcifies the form of" \
                " message being printed back upon successfull retrieval of jobs" \
                " list. Must be a python format() string consuming at least"
                " the {jID} and {jState} variable (rest are backend-specific)."
        }
    }
    __defaults = {
        'result_format' : 'jID={jID} jState={jState}'
    }
    def list_jobs(self, backendArguments=[]):
        try:
            r = self.backend.list_jobs( backendArguments=backendArguments )
        except SubmissionFailure as e:
            sys.stderr.write( 'Submission error occured: rc=%s\n'%e.output['rc'] )
            if not e.exception:
                L.error( '<submission command stdout>:\n' )
                L.error( e.output['stdout'].decode('ascii') )
                L.error( '<submission command stderr>:\n' )
                L.error( e.output['stderr'].decode('ascii') )
            else:
                L.exception( e.exception )
        return r
    def _main( self
             , backend=None, backendConfig=None
             , backendArguments=[]
             , resultFormat='' ):
        """
        Defines argument parser object for possible future usage.
        """
        L = logging.getLogger(__name__)
        self._backendName, self._backendConfig = backend, backendConfig
        r = self.list_jobs(backendArguments=backend_specific_args( backendArguments, backend ))
        sys.stdout.write( resultFormat.format(**r) )
        return 0

# TODO: BatchQueryStatusTask -> get_status(self, jID, popenKwargs={}):
# TODO:     BatchKillJobTask -> kill_job(self, jID, popenKwargs={}):
# TODO:  BatchWaitForJobTask -> wait_for_job(self, jID, intervalSecs=60, popenKwargs={}):
# TODO:    BatchDumpLogsTask -> dump_logs_for( self, jID, popenKwargs={} ):

def main():
    """
    Function routing to certain procedure.
    """
    lamia.logging.setup()
    L = logging.getLogger(__name__)
    procedure = sys.argv[1] if len(sys.argv) > 1 else ''
    t = None
    if 'submit' == procedure:
        t = BatchSubmittingTask()
    elif 'list' == procedure:
        t = BatchListingTask()
    elif 'status' == procedure:
        pass
    elif 'kill' == procedure:
        pass
    elif 'dump-logs' == procedure:
        pass
    elif 'wait' == procedure:
        pass
    return t.run(sys.argv[2:])
    if not t:
        L.error( 'Bad procedure name given. Expected one of:\n' )
        L.error( '  submit, status, kill, dump-logs, wait\n' )
        L.error( 'To get help on certain procedure name, invoke with:\n' )
        L.error( '  $ %s <procedureName> -h\n'%sys.argv[0] )
        return 1

if "__main__" == __name__:
    ret = main()
    sys.exit(ret)

