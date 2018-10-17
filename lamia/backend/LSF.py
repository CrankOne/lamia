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

import shlex, subprocess, re, logging, sys, copy, time
import lamia.backend.interface

# A regex to parse the LSF message about job being successfully submitted:
rxJSubmitted = re.compile(r'^Job <(?P<jID>\d+)> is submitted to(?: default)? queue <(?P<queue>[^>]+)>\.$')
# A regex to parse `bsub -wX' output about jobs being currently active or
# being recently done (`bsub -wXd).
rxJList = re.compile( r'^(?P<jID>\d+)\s+(?P<user>\w+)\s+(?P<jState>[A-Z]+)\s+(?P<queue>\w+)\s+(?P<submHost>[\w\.]+)\s+(?P<execHost>[\w.\-]+)\s+(?P<jName>[\w.\-\[\]]+)\s+(?P<jSubTime>.+?)\s*$' )
# All these entities has a bitflags of following meaning:
#   0x1 denotes the general error
#   0x2 means that we can wait for the job to finish
gLSFJobStates = {
        'PEND' : 0x2,
        'RUN' : 0x2,
        'DONE' : 0x0,
        'EXIT' : 0x0,  # yeah, but this process may hang few minutes still...
        'WAIT' : 0x2,
        'PSUSP' : 0x2,
        'USUSP' : 0x2,
        'SSUSP' : 0x2,
        'UNKWN' : 0x1
    }
# Default backend-specific settings:
gDefaults = {
        # Where to find executables responsible for various tasks
        'execs' : {
            'bsub' : 'bsub',
            'bjobs' : 'bjobs'
        },
        # LSF-specific job submission settings
        'bsub'  : {},
        'bpeek' : {},
        'bkill' : {},
        'bjobs' : { 'noheader': None
                  , 'wX' : None }
    }


class LSFBackend(lamia.backend.interface.BatchBackend):
    """
    The batch-submitting implementation for LSF.
    """
    
    def backend_type():
        return 'LSF'

    
    def __init__( self, config ):
        super().__init__(config)

    def _bjobs(self, cmd_, timeout=30, popenKwargs={}):
        L = logging.getLogger(__name__)
        # Submit the job and check its result.
        try:
            # Sets the default popen's kwargs and override it by user's kwargs
            pkw = copy.deepcopy({ 'stdout' : subprocess.PIPE
                                , 'stderr' : subprocess.PIPE
                                , 'universal_newlines' : True })
            pkw.update(popenKwargs)
            bjP = subprocess.Popen( cmd_, **pkw )
            L.debug('Performing subprocess invocation:')
            L.debug("  $ %s"%(' '.join(cmd_)) )
            L.debug("Supplementary popen() arguments: %s."%str(pkw) )
            out, err = bjP.communicate( timeout=timeout )
            rc = bjP.returncode
            #m = rxJSubmitted.match( out.decode('ascii') )  # TODO
        except Exception as e:
            raise lamia.backend.interface.JListFailure( exception=e )
        if 0 != rc:
            raise lamia.backend.interface.JListFailure(
                    output={ 'stdout' : out
                           , 'stderr' : err
                           , 'rc' : rc })
        jobsList = []
        for l in out.split('\n'):
            if not l: continue  # omit blank lines
            m = rxJList.match(l)
            if not m:
                L.warning('Unable to interpret bjobs output line: "%s"'%l)
                continue
            jobsList.append(m.groupdict())
        L.debug( 'bjobs output of %d entries treated'%len(jobsList) )
        return jobsList

    def submit( self, jobName
                    , cmd=None
                    , stdout=None, stderr=None
                    , timeout=30
                    , backendArguments={}
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
        bsubArgs = copy.deepcopy(self.cfg['bsub'])
        bsubArgs.update(backendArguments)
        # Form the LSF submission arguments
        for k, v in bsubArgs.items():
            cmd_.append( '-%s'%k )
            if v is not None:
                cmd_.append(str(v))
        if 'q' not in bsubArgs.keys():
            raise RuntimeError('LSF queue is not specified')  # TODO: warning
        cmd_.append( '-J%s'%jobName )
        cmd_.append( '-oo%s'%stdout )
        cmd_.append( '-eo%s'%stderr )
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
            raise TypeError( "First argument for submit is expected to be' \
                    ' either str or list. Got %s."%type(cmd) )
        if cmd:
            cmd_ += copy.deepcopy(cmd)
        # Submit the job and check its result.
        try:
            # Sets the default popen's kwargs and override it by user's kwargs
            pkw = copy.deepcopy({ 'stdout' : subprocess.PIPE
                                , 'stderr' : subprocess.PIPE
                                , 'universal_newlines' : True })
            pkw.update(popenKwargs)
            submJob = subprocess.Popen( cmd_, **pkw )
            L.debug('Performing subprocess invocation:')
            L.debug("  $ %s"%(' '.join(cmd_) if stdinCmds is None else '<stdin>' ))
            L.debug("Supplementary popen() arguments: %s."%str(pkw) )
            if stdinCmds is not None:
                L.debug( "--- begin of forwarded input from stdin ---" )
                L.debug( stdinCmds )
                L.debug( "--- end of forwarded input from stdin ---" )
                out, err = submJob.communicate( input=stdinCmds, timeout=timeout )
            else:
                out, err = submJob.communicate( timeout=timeout )
            rc = submJob.returncode
            m = rxJSubmitted.match( out ) #.decode('ascii') )
        except Exception as e:
            raise lamia.backend.interface.SubmissionFailure( exception=e )
        if not m or 0 != rc:
            raise lamia.backend.interface.SubmissionFailure(
                    output={ 'stdout' : out
                           , 'stderr' : err
                           , 'rc' : rc })
        L.info( 'LSF job submitted: {queue}/{jID}'.format(**m.groupdict()) )
        return int(m.groupdict()['jID']), dict(m.groupdict())

    def list_jobs(self, timeout=30, backendArguments={}, popenKwargs={}):
        L = logging.getLogger(__name__)
        # Form the full bjobs tuple:
        #- Prepare the bsub arguments:
        cmd_ = [self.cfg['execs.bjobs']]
        bjobsArgs = copy.deepcopy(self.cfg['bjobs'])
        bjobsArgs.update(backendArguments)
        # Form the LSF bjobs arguments
        for k, v in bjobsArgs.items():
            cmd_.append( '-%s'%k )
            if v is not None:
                cmd_.append(str(v))
        jLst = self._bjobs( cmd_, timeout=timeout, popenKwargs=popenKwargs )
        # Repeat, to obtain jobs what are recently done
        cmd_.append( '-d' )
        jLst += self._bjobs( cmd_, timeout=timeout, popenKwargs=popenKwargs )
        return jLst

    def get_status( self, jID
                  , backendArguments={}
                  , timeout=30
                  , popenKwargs={}):
        """
        By given `jID' (of possibly arbitrary type), shall return "active job
        properties object".
        """
        L = logging.getLogger(__name__)
        # Form the full bjobs tuple:
        #- Prepare the bsub arguments:
        cmd_ = [self.cfg['execs.bjobs']]
        bjobsArgs = copy.deepcopy(self.cfg['bjobs'])
        bjobsArgs.update(backendArguments)
        # Form the LSF bjobs arguments
        for k, v in bjobsArgs.items():
            cmd_.append( '-%s'%k )
            if v is not None:
                cmd_.append(str(v))
        cmd_.append( '%d'%jID )
        jLst = self._bjobs( cmd_, timeout=timeout, popenKwargs=popenKwargs )
        # Repeat, to obtain jobs what are recently done
        #cmd_.append( '-d' )
        #jLst += self._bjobs( cmd_, timeout=timeout, popenKwargs=popenKwargs )
        return jLst

    def kill_job(self, jID, popenKwargs={}):
        """
        By given `jID' (of possibly arbitrary type), shall initiate job
        interruption process (possibly asynchroneous).
        """
        pass

    def wait_for_job( self, jID
                    , nAttempts=0
                    , intervalSecs=60
                    , popenKwargs={}
                    , report=True ):
        """
        TODO: support for job arrays. See, e.g.:
            https://www.ibm.com/support/knowledgecenter/en/SSETD4_9.1.3/lsf_admin/job_arrays_lsf.html
            https://www.ibm.com/support/knowledgecenter/SSETD4_9.1.3/lsf_admin/job_array_create.html
        """
        L = logging.getLogger(__name__)
        nAttempt = 0
        # Kludge: here we waiting 5 secs due to LSF feature of not showing the
        # job in bjobs list immediately after submission.
        #time.sleep(5) # TODO: is it true?
        while True:
            nAttempt += 1
            jLst = self.get_status( jID, popenKwargs=popenKwargs )
            if len(jLst) == 0 or (nAttempts != 0 and nAttempt >= nAttempts):
                L.warning("Exit waiting loop due to end or number"
                    " of attempts exceeded or none job with such ID"
                    " found.")
                break
            assert( 1 == len(jLst))
            jState = jLst[0]['jState']
            jStCode = gLSFJobStates.get(jState, 0x2)
            if 0x2 & jStCode:
                if report:
                    L.info( 'Job %d has "%s" status, waiting%s.'%(jID, jState,
                        ' %d/%d'%(nAttempt, nAttempts) if nAttempts else '' ) )
                time.sleep(intervalSecs)
            else:
                L.info( 'Done waiting for LSF job %d, state: "%s"'%(jID, jState) )
                break  # Exit due to `done' probably
            if 0x1 & jStCode:
                L.error("LSF job %d has erroneous/unknown status: \"%s\"."%jState )

    def dump_logs_for(self, jID, popenKwargs={}):
        pass

