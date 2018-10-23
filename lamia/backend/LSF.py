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
            'bsub' : '/usr/bin/bsub',
            'bjobs' : '/usr/bin/bjobs'
        },
        # LSF-specific job submission settings
        'bsub'  : {},
        'bpeek' : {},
        'bkill' : {},
        'bjobs' : { 'noheader': None
                  , 'wX' : None }
    }

# A special shell scrpt template performing
gShell = """
#!/bin/bash
args = (
    %s
)
IFS=';' {command} ${args[$LSB_JOBINDEX]}
"""

class LSFSubmission(lamia.backend.interface.Submission):
    """
    An LSF job submission representation.
    Ctr makes everything ready for direct command-shell `bsub' invocation.
    """
    @staticmethod
    def macros():
        return { 'jIndex' : '%I'
               , 'jID' : '%J' }

    @property
    def jobName(self):
        """
        Overrides default property of `Submission' class
        """
        if not self.isImplicitArray and 1 == self.nProcs:
            return super().jobName
        else:
            n = self.nProcs
            if hasattr(self, 'nImplicitJobs') and self.nImplicitJobs > 1:
                n *= self.nImplicitJobs
            return '%s[1-%d]'%(super().jobName, n)

    @property
    def cmdArgs(self):
        """
        Returns the command to be forwarded to the os.exec()/subprocess.popen()
        calls for actual submission.
        Presumes that `self.bsubExec' and `self.bsubArgs' are set.
        """
        L = logging.getLogger(__name__)
        c = [self.bsubExec]
        # Form the LSF submission arguments
        for k, v in self.bsubArgs.items():
            c.append( '-%s'%k )
            if v is not None:
                c.append(str(v).format(**self.macros()))
        c.append( '-J%s'%self.jobName )
        # TODO: dependencies!
        return c + self.bsubTarget

    def compose_array_script(self, execTarget, tArgs, submissionFilePath=None):
        """
        There is no means in LSF to express varible arguments within an array.
        The only thing that differs within the job context is `LSB_JOBINDEX'
        environment variable, so we hide command-line argument iteration within
        the encompassing synthesized shell script.
        """
        if submissionFilePath is None:
            dn, fexec = os.path.split(execTarget)
            submissionFilePath = os.path.join( dn, fexec + '.LSF.sh' )
        self.nImplicitJobs = 0
        with open(submissionFilePath) as f:
            f.write("#!/bin/bash\n")
            f.write("# Shell script to be processed on LSF batch.\n")
            f.write("cmdArgs=(\n")
            for n, argTuple in enumerate(lamia.backend.interface.expand_cmd_args(tArgs)):
                f.write('  ')
                f.write( ';'.join(argTuple) )
                f.write('  # %d\n'%n )
                self.nImplicitJobs += 1
            f.write(")\n")
            f.write("IFS=\"%s\" %s ${cmdArgs[$LSB_JOBINDEX]}")
            f.write("exit $?")
            L.info('LSF array-dispatching script for %d entries'
                    ' has been written in "%s".'%(nEntries, submissionFilePath))
        os.chmod(submissionFilePath, 0o755)
        return submissionFilePath

    def __init__(self, jobName, cfg
                     , cmd=None
                     , nProcs=1
                     , stdout=None, stderr=None
                     , backendArguments={}
                     , popenKwargs={} ):
        """
        ...
        """
        L = logging.getLogger(__name__)
        # Set up bsub, pre-form/validate data for command line invocation
        self.bsubExec = cfg['execs.bsub']
        self.bsubArgs = copy.deepcopy(cfg['bsub'])
        self.bsubArgs.update(backendArguments)
        for k in ['J', 'oo', 'eo', 'o', 'e']:
            v = self.bsubArgs.pop(k, None)
            if v:
                L.warning( '\"-%s\"%s LSF backend argument will be ignored in'
                    ' favor of one defined by LSF'
                    ' back-end.'%(k, '="%s"'%str(v) if v else '') )
        if 'q' not in self.bsubArgs.keys():
            L.warning('LSF queue is not specified.'
                    ' Default LSF queue will be used.')
        self.bsubArgs['oo'] = stdout
        self.bsubArgs['eo'] = stderr
        # Initialize basic parent properties:
        super().__init__( jobName, cmd, nProcs )
        # Now, treat the target command in LSF way.
        if self.isImplicitArray:
            self.bsubTarget = \
                [self.compose_array_script( self.tCmd[0], self.tCmd[1:],
                        submissionFilePath=backendArguments.get('submissionFilePath', None))]
        else:
            self.bsubTarget = copy.deepcopy(cmd)
        # Sets the default popen's kwargs and override it by user's kwargs
        self.pkw = copy.deepcopy({ 'stdout' : subprocess.PIPE
                                 , 'stderr' : subprocess.PIPE
                                 , 'universal_newlines' : True })
        self.pkw.update(popenKwargs)

class LSFBackend(lamia.backend.interface.BatchBackend):
    """
    The batch-processing back-end implementation for LSF.
    """
    def backend_type():
        return 'LSF'

    def __init__( self, config ):
        super().__init__(config)

    def _bjobs(self, cmd_, popenKwargs={}):
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
            out, err = bjP.communicate( timeout=self.cfg['timeouts']['bjobs'] )
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

    def _submit(self, j):
        """
        Internal method: performs shell invocation of submission util. Doesn't
        take care of dependencies, command line args, etc: just forwards it's
        signature to shell.
        """
        L = logging.getLogger(__name__)
        # Submit the job and check its result.
        try:
            submJob = subprocess.Popen( j.cmdArgs, **j.pkw )
            L.debug('Performing subprocess invocation:')
            L.debug("  $ %s"%(' '.join(j.cmdArgs) if not j.stdinTarget else '<stdin>' ))
            L.debug("Supplementary popen() arguments: %s."%str(j.pkw) )
            if j.stdinTarget:
                L.debug( "--- begin of forwarded input from stdin ---" )
                L.debug( j.stdin )
                L.debug( "--- end of forwarded input from stdin ---" )
                out, err = submJob.communicate( input=j.stdin
                            , timeout=self.cfg['timeouts']['bsub'] )
            else:
                out, err = submJob.communicate(
                            timeout=self.cfg['timeouts']['bsub'] )
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
        return dict(m.groupdict())

    def queue( self, jobName, **kwargs ):
        return LSFSubmission(jobName, self.cfg, **kwargs)

    def dispatch_jobs(self, j):
        assert( isinstance(j, LSFSubmission) )
        if j.dependencies:
            raise NotImplementedError("Dependencies is not yet supported.")  # TODO
        return self._submit( j )

    def list_jobs(self, backendArguments={}, popenKwargs={}):
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
        jLst = self._bjobs( cmd_, popenKwargs=popenKwargs )
        # Repeat, to obtain jobs what are recently done
        cmd_.append( '-d' )
        jLst += self._bjobs( cmd_, popenKwargs=popenKwargs )
        return jLst

    def get_status( self, subObj
                  , backendArguments={}
                  , popenKwargs={}):
        """
        By given `subObj' (of possibly arbitrary type), shall return "active job
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
        cmd_.append( '{jID}'.format(**subObj) )
        jLst = self._bjobs( cmd_, popenKwargs=popenKwargs )
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

    def wait_for_job( self, subObj
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
        while True:
            nAttempt += 1
            jLst = self.get_status( subObj, popenKwargs=popenKwargs )
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
                    L.info( 'Job %s has "%s" status, waiting%s.'%(subObj['jID'], jState,
                        ' %d/%d'%(nAttempt, nAttempts) if nAttempts else '' ) )
                time.sleep(intervalSecs)
            else:
                L.info( 'Done waiting for LSF job %s, state: "%s"'%(subObj['jID'], jState) )
                break  # Exit due to `done' probably
            if 0x1 & jStCode:
                L.error("LSF job %d has erroneous/unknown status: \"%s\"."%jState )

    def dump_logs_for(self, jID, popenKwargs={}):
        pass

