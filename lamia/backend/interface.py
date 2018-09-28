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
import lamia.core.configuration, lamia.logging

rxArg = re.compile(r'^(?P<key>\w+)(?P<backend>:\w+)?=(?P<value>.*)$')

class SubmissionFailure(RuntimeError):
    def __init__(self, output={'stdout':None, 'stderr':None, 'rc':None}
                     , exception=None):
        self.output = output
        self.exception = exception
        message = "Job submission error occured."
        if self.exception:
            message += "An \"%s\" exception occured while subprocessing."%(str(exception))
        else:
            message += "See `output' property(-ies) associated."
        super().__init__(message)

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
    """
    def __init__( self, config ):
        L = logging.getLogger(__name__)
        self.cfg = lamia.core.configuration.Stack()
        self.cfg.push(lamia.core.configuration.Configuration(config))

    @property
    @abc.abstractmethod
    def backend_type(self):
        pass

    @abc.abstractmethod
    def submit(self, jobName
                   , cmd=None
                   , stdout=None, stderr=None
                   , timeout=30
                   , submArgs={}
                   , popenKwargs={} ):
        """
        Shall submit job and, upon successful submission, return the "job
        submitted properties" object.
        The `cmd' must be either a list of shell command arguments to submit,
        or the entire command, or None/'-' indicating that input from stdin
        has to be retrieved.
        The submArgs is an optional parameters usually provided to
        submission command, steering the submission process itself. Here, they
        overrides what is given to ctr.
        The `popenKwargs' is rarely used dictionary of arguments forwarded to
        Python's subprocess.Popen() ctr.
        """
        pass

    @abc.abstractmethod
    def get_status(self, jID, popenKwargs={}):
        """
        By given `jID' (of possibly arbitrary type), shall return "active job
        properties object"
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
    def wait_for_job(self, jID, intervalSecs=60, popenKwargs={}):
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

def instantiate_backend( name, config, *args, **kwargs ):
    """
    A virtual constructor for back-end instances: creates particular back-end
    instance based on its string name (cf. factory).
    """
    backEnds = {}
    if not BatchBackend.__subclasses__():
        L.error( "No back-ends available. Giving up." )
        sys.exit(1)
    for c in BatchBackend.__subclasses__():
        if c.backend_type() == name:
            return c(config, *args, **kwargs)
    raise LookupError("Unable to find batch back-end"
            " interface implementation \"%s\"."%name)

#
# Utility imperatives
####################

def argparse_add_common_args(p):
    p.add_argument( '-A', '--argument', help="An argument to be forwarded" \
            " to back-end command shell invokation. Must be avoided in mature" \
            " code, but is still useful for the debug and development." \
            " Expected to be given in form <key>[:<backend>]=<value>." \
            " The <backend> parameter is optional and makes this " \
            " specification to be only active for certain back-end."
            , action='append' )
    p.add_argument( '-B', '--backend', help="One of the batch back-ends" \
            " available. Available: %s."%( ','.join([ c.backend_type() \
                    for c in BatchBackend.__subclasses__() ]) \
                    if len(BatchBackend.__subclasses__()) else \
            'None back-ends are available. Consider loading some prior to' \
            'run this code.'), required=True )
    p.add_argument( '--backend-config', help="Configuration file for the backend to"
            " be used.", required=False )

def job_submit_main(cmdArgs):
    """
    Defines argument parser object for possible future usage.
    """
    L = logging.getLogger(__name__)
    L.debug('job_submit() invoked with: %s'%str(cmdArgs))
    p = argparse.ArgumentParser( description="A job-submission wrapper for LSF.")
    p.add_argument( '-f', '--result-format', help="Sepcifies the form of" \
            " message being printed back upon successfull job submission." \
            " Must be a python format() string consuming at least the {jID}"\
            " variable (rest are backend-specific).",
            default='jID={jID}' )
    p.add_argument( '-o', '--stdout-log', help="Specifies a file where" \
            " job's stdout has to be written." )
    p.add_argument( '-e', '--stderr-log', help="Specifies a file where" \
            " job's stdout has to be written." )
    p.add_argument( '-J', '--job-name', help="A name of the job."
                  , required=True )
    p.add_argument( 'fwd', nargs=argparse.REMAINDER )
    argparse_add_common_args(p)
    args = p.parse_args(cmdArgs)
    L.debug( 'Parsed: %s'%(str(args)) )
    submArgs={}
    for strPair in args.argument or []:
        m = rxArg.match(strPair)
        if not m:
            raise ValueError('Unable to interpret submission argument' \
                    ' expression "%s".'%strPair )
        if 'backend' in m.groupdict().keys() \
        and args.backend != m.groupdict()['backend']:
            L.debug("Parameter `%s:%s=%s' is omitted (using %s)."%(
                    m.groupdict()['key'],
                    m.groupdict()['backend'],
                    m.groupdict()['value'],
                    args.backend ))
            continue
        submArgs[m.groupdict()['key']] = m.groupdict()['value']
    B = instantiate_backend(args.backend, args.backend_config)
    try:
        r = B.submit( args.job_name
                    , cmd=args.fwd
                    , stdout=args.stdout_log, stderr=args.stderr_log
                    , submArgs=submArgs )
    except SubmissionFailure as e:
        sys.stderr.write( 'Submission error occured: rc=%s\n'%e.output['rc'] )
        if not e.exception:
            L.error( '<submission command stdout>:\n' )
            L.error( e.output['stdout'].decode('ascii') )
            L.error( '<submission command stderr>:\n' )
            L.error( e.output['stderr'].decode('ascii') )
        else:
            L.exception( e.exception )
    #print( args.result_format.format(**r) )
    return 0

def main():
    """
    Function routing to certain procedure.
    """
    L = logging.getLogger(__name__)
    procedure = sys.argv[1] if len(sys.argv) > 1 else ''
    if 'submit' == procedure:
        return job_submit_main( sys.argv[2:] )
    elif 'status' == procedure:
        pass
    elif 'kill' == procedure:
        pass
    elif 'dump-logs' == procedure:
        pass
    elif 'wait' == procedure:
        pass
    else:
        L.error( 'Bad procedure name given. Expected one of:\n' )
        L.error( '  submit, status, kill, dump-logs, wait\n' )
        L.error( 'To get help on certain procedure name, invoke with:\n' )
        L.error( '  $ %s <procedureName> -h\n'%sys.argv[0] )
        return 1

if "__main__" == __name__:
    lamia.logging.setup(defaultPath='lamia/assets/configs/logging.yaml')
    ret = main()
    sys.exit(ret)

