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

import abc, os, logging, sys, copy, argparse
import lamia.core.configuration, lamia.logging

class SubmissionFailure(RuntimeError):
    def __init__(self, output={}, exception=None):
        self.output = output
        self.exception = exception
        message = "Job submission error occured. "
        if self.exception:
            message += "An \"%s\" exception occured while subprocessing."%(str(exception))
        else:
            message += "See `output' property(-ies) associated."
        super().__init__(message)

class BatchBackend(abc.ABC):
    """
    Defines basic properties system for every batch-processing backend.
    The few abstract method designed for job submission, its status retreival
    and interruption.
    """
    def __init__( self, taskName ):
        L = logging.getLogger(__name__)
        self.cfg = lamia.core.configuration.Stack()
        self.cfg.push({
                # An arbitrary expression to uniqely identify the current
                # session
                'sessionTag' : os.environ.get('TTAG', '%x'%int(datetime.datetime.now().timestamp())),
                'taskName' : taskName,
                # The pattern for log files path. All the self.cfg object will
                # be used for formatting + the `logType'=(out|err) strings.
                'jobStdout' : '/tmp/%(taskName)s.%(sessionTag)s.%(backendType)s.%(jobName)s.%(logType)s.txt'
            })

    @property
    @abc.abstractmethod
    def backend_type(self):
        pass

    @abc.abstractmethod
    def submit(self, cmd
                   , jobName
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

#

def mk_arg_parser():
    """
    Defines argument parser object for possible future usage.
    """
    p = argparse.ArgumentParser( description="A job-submission wrapper for LSF.")
    p.add_argument( 'procedure', help="The procedure to invoke." )
    p.add_argument( 'fwd', nargs=argparse.REMAINDER )
    p.add_argument( '-A', '--argument', help="An argument to be forwarded" \
            " to back-end command shell invokation. Must be avoided in mature" \
            " code, but is still useful for the debug and development." )
    p.add_argument( '-b', '--backend', help="One of the batch back-ends" \
            " available. Available: %s."%( ','.join([ c.backend_type() \
                    for c in BatchBackend.__subclasses__() ]) \
                    if len(BatchBackend.__subclasses__()) else \
            'None back-ends are available. Consider loading some prior to' \
            'run this code.') )
    #p.add_argument( '--config', help="Configuration file for the backend to"
    #        " be used." )
    return p

def main():
    L = logging.getLogger(__name__)
    args = mk_arg_parser().parse_args()
    backEnds = {}
    if not BatchBackend.__subclasses__():
        L.error( "No back-ends available. Giving up." )
        sys.exit(1)
    for c in BatchBackend.__subclasses__():
        backEnds[c.backend_type()] = c
    L.debug( 'Invoked with: %s'%(str(args)) )
    B = c()
    if 'submit' == args.procedure:
        r = B.submit( args.fwd )
    elif 'kill' == args.procedure:
        raise NotImplementedError('LSF-kill')  # TODO
    elif 'status' == args.procedure:
        raise NotImplementedError('LSF-status')  # TODO
    elif 'wait' == args.procedure:
        raise NotImplementedError('LSF-wait')  # TODO
    else:
        raise LookupError( 'Unable to perform procedure `%s.\''%args.procedure )

if "__main__" == __name__:
    lamia.logging.setup(defaultPath='lamia/assets/configs/logging.yaml')
    ret = main()
    sys.exit(ret)

