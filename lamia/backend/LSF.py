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

import shlex, subprocess, re, logging, sys, copy
import lamia.backend.interface

# A regex to parse the LSF message about job being successfully submitted:
rxJobSubmitted = re.compile(r'^Job <(?P<jID>\d+)> is submitted to(?: default)? queue <(?P<queue>[^>]+)>\.$')
# Default backend-specific settings:
gDefaults = {
        # Where to find executables responsible for various tasks
        'execs' : {
            'bsub' : 'bsub'
        },
        # LSF-specific job submission settings
        'bsub'  : {},
        'bpeek' : {},
        'bkill' : {},
        'bjobs' : {}
    }


class LSFBackend(lamia.backend.interface.BatchBackend):
    """
    The batch-submitting implementation for LSF.
    """
    def backend_type():
        return 'LSF'

    def __init__( self, config ):
        super().__init__(config)

    def submit( self, jobName
                    , cmd=None
                    , stdout=None, stderr=None
                    , timeout=30
                    , submArgs={}
                    , popenKwargs={} ):
        """
        Will forward `cmd' as a string or a tuple within the `subprocess.Popen'
        call treating its return code and stdout/stderr.
        Upon successful submission will return job `ID' and `queue' information
        about job just being submitted.
        Will raise `LSFSubmissionFailure' on failure.
        """
        L = logging.getLogger(__name__)
        # Form the full bsub tuple:
        #- Prepare the bsub arguments:
        cmd_ = [self.cfg['execs.bsub']]
        bsubArgs = {} #copy.deepcopy(self.cfg['bsub'])
        bsubArgs.update(submArgs)
        # Form the LSF submission arguments
        for k, v in bsubArgs.items():
            cmd_.append( '-%s'%k )
            if v is not None:
                cmd_.append(str(v))
        cmd_.append( '-J%s'%jobName )
        cmd_.append( '-o%s'%stdout )
        cmd_.append( '-e%s'%stderr )
        #- Append the command:
        stdinCmds = None
        if type(cmd) is None \
        or (type(cmd) is str and '-' == cmd) \
        or not cmd:
            stdinCmds = ''
            # Read from stdin
            for line in sys.stdin:
                stdinCmds += line
            L.debug( "Stdin input: %s"%stdinCmds )
            if not stdinCmds:
                raise ValueError( "Empty stdin input given for job submission." )
        elif type(cmd) is str:
            cmd_ += shlex.split(cmd)
        elif type(cmd_) is not list:
            raise TypeError( "Forst argument for submit is expected to be' \
                    ' either str or list. Got %s."%type(cmd) )
        if cmd:
            cmd_ += copy.deepcopy(cmd)
        # Submit the job and check its result.
        try:
            # Sets the default popen's kwargs and override it by user's kwargs
            pkw = copy.deepcopy({ 'stdout' : subprocess.PIPE
                                , 'stderr' : subprocess.PIPE })
            pkw.update(popenKwargs)
            submJob = subprocess.Popen( cmd_, **pkw )
            L.debug('Performing subprocess invocation:')
            L.debug("  $ %s"%(' '.join(cmd_) if stdinCmds is not None else '<stdin>' ))
            L.debug("Supplementary popen() arguments: %s."%str(pkw) )
            if stdinCmds is not None:
                L.debug( "--- begin of forwarded input from stdin ---" )
                L.debug( stdinCmds )
                L.debug( "--- end of forwarded input from stdin ---" )
                out, err = submJob.communicate( input=stdinCmds, timeout=timeout )
            else:
                out, err = submJob.communicate( timeout=timeout )
            rc = submJob.returncode
            m = rxJobSubmitted.match( out.decode('ascii') )
        except Exception as e:
            raise lamia.backend.interface.SubmissionFailure( exception=e )
        if not m or 0 != rc:
            raise lamia.backend.interface.SubmissionFailure(
                    output={ 'stdout' : out
                           , 'stderr' : err
                           , 'rc' : rc })
        L.info( 'LSF job submitted: {queue}/{jID}'.format(**m.groupdict()) )
        return m.groupdict()['jID'], m.groupdict()['queue']

    def get_status(self, jID, popenKwargs={}):
        """
        By given `jID' (of possibly arbitrary type), shall return "active job
        properties object"
        """
        pass

    def kill_job(self, jID, popenKwargs={}):
        """
        By given `jID' (of possibly arbitrary type), shall initiate job
        interruption process (possibly asynchroneous).
        """
        pass

    def wait_for_job(self, jID, popenKwargs={}):
        pass

    def dump_logs_for(self, jID, popenKwargs={}):
        pass

