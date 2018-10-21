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
"""
The shell utilities to the HTCondor facility is the most elaborated way to
interact with its interfaces (and actually an only full-fledged one).
"""
import logging, re, os, copy, subprocess
import lamia.backend.interface

# HTCondor job ID syntax, ususally consisting of <clusterID>.<ProcessID>
rxsJID = r'\d+\.\d+'
rxJSubmitted = re.compile(r'(?P<JIDRngBgn>' + rxsJID \
            + ')\s+-\s+(?P<JIDRngEnd>' + rxsJID + ')' )
rxJList = re.compile(r'^(?P<jobID>\d+\.\d+)\s+(?P<user>\w+)\s+(?P<submTimedate>\d{1,2}\/\d{1,2}\s+[\d:]+)\s+(?P<runTime>[\d+:]+)\s+(?P<jobState>[>HRICXS<])\s+(?P<priority>\d+)\s+(?P<memSize>\d+\.\d+)\s+(?P<cmd>.+)$')

# Default backend-specific settings:
gDefaults = {
        # Where to find executables responsible for various tasks
        'execs' : {
            'condorSubmit' : '/usr/bin/condor_submit',
        },
        # HTCondor-specific config ("classAds")
        'classAds' : {
            'submit' : {
                'universe' : 'vanilla',
                'should_transfer_files' : 'YES',
                'when_to_transfer_output' : 'ON_EXIT'
            }
        }
    }

class HTCondorShellBackend(lamia.backend.interface.BatchBackend):
    """
    The batch-processing back-end implementation for HTCondor.
    Relies on manually-written ClassAd files and shell utilities.
    """

    def backend_type():
        return 'HTCondorShell'

    def __init__(self, config):
        super().__init__(config)

    def submit(self, jobName,
                     cmd=None,
                     nProcs=1,
                     stdout=None, stderr=None,
                     timeout=30,
                     backendArguments={},
                     popenKwargs={} ):
        """
        Submit the job to HTCondor
        Will forward `cmd' as a string within the `subprocess.Popen'.

        Important `backendArguments' entry is a "submissionFile" that shall denote a
        file where corresponding submission classAd will be generated. If it
        is not provided, the first `cmd' entry will be considered as a filename
        to which we append a `.sub' postfix and use resulting path for
        generating a submission file.
        """
        assert(nProcs)
        assert(stdout)
        assert(stderr)
        L = logging.getLogger(__name__)
        if type(cmd) is None \
        or (type(cmd) is str and '-' == cmd) \
        or not cmd:
            # TODO: consider to use `-interactive' to `condor_sub'
            raise NotImplementedError("Input from stdin for HTCondor backend.")
        if type(cmd) is str:
            cmd = [cmd]
        elif type(cmd) is not list:
            raise TypeError( 'First argument is expected to be a list' \
                            ' not a `%s\'.'%type(cmd) )
        # NOTE: the native `classad' module's instances seems to be pretty
        # useless due to their rudimentary serialization mechanism. Writing the
        # submission file ad-hoc seems to be a better alternative since ClassAd
        # syntax is pretty straightforward, even what is concerned `queue'
        # keyword.
        cad = copy.deepcopy(self.cfg['classAds.submit'])
        cad["executable"] = os.path.abspath(cmd[0])
        if 'submissionFile' not in backendArguments:
            dn, fexec = os.path.split(cad["executable"])
            submissionFilePath = os.path.join( dn, fexec + '.htcondor-sub')
        else:
            submissionFilePath = backendArguments['submissionFile']
        if 'userLogFile' not in backendArguments:
            dn, fexec = os.path.split(cad["executable"])
            uLogFilePath = os.path.join( dn, fexec + '.htcondor-log')
        else:
            uLogFilePath = backendArguments['userLogFile']
        if len(cad) > 1:
            cad["arguments"] = cmd[1:]
        htcndrMacros = { 'jIndex' : '$(Process)'
                       , 'jID' : '$(Cluster).$(Process)' }
        cad.update({
            "output" : stdout.format(**htcndrMacros),
            "error" : stderr.format(**htcndrMacros),
            "userLog" : uLogFilePath
        })
        if 'classAd' in backendArguments:
            cad.update( backendArguments['classAd'] )
        if 'environment' in cad:
            assert(type(cad['environment'] is dict))
            htcondorJobIndexVal = 'SINGLE' if 1 == nProcs else '$(Process)'
            if 'HTCONDOR_JOBINDEX' in cad['environment']:
                L.error( "The `HTCONDOR_JOBINDEX' specified for the"
                        " nevironment will be overriden"
                        " with \"%s\"."%htcondorJobIndexVal )
            cad['HTCONDOR_JOBINDEX'] = htcondorJobIndexVal
            # NOTE: we do not escape the double quotes here (acc. to
            # `man condor_submit' it has been done with double-quotes ("")),
            # making this to be a user responsibility.
            s = '"%s"'%(' '.join(['%s=%s'%(k, v) for k, v in cad['environment'].items()]))
        with open(submissionFilePath, 'w') as f:
            for k, v in cad.items():
                if type(v) is list \
                or type(v) is tuple:
                    strV = ' '.join(v)
                elif type(v) in (int, float, str):
                    strV = str(v)
                else:
                    raise TypeError('Can not serialize type `%s\' into classAd'
                        ' file.'%type(v).__name__ )
                f.write( '%s = %s\n'%(k, strV) )
        # Submission command:
        cmd_ = [ self.cfg['execs.condorSubmit'], submissionFilePath
               , '-terse'
               , '-batch-name', jobName
               , '-queue', '%d'%nProcs  #< must be last cmd arg!
               ]
        try:
            pkw = copy.deepcopy({ 'stdout' : subprocess.PIPE
                                , 'stderr' : subprocess.PIPE
                                , 'universal_newlines' : True })
            pkw.update(popenKwargs)
            L.debug("Supplementary popen() arguments: %s."%str(pkw) )
            submJob = subprocess.Popen(cmd_, **pkw)
            out, err = submJob.communicate( timeout=timeout )
            rc = submJob.returncode
            L.debug('condor_submit stdout: <<%s>>'%out)
            m = rxJSubmitted.match( out )
        except Exception as e:
            raise lamia.backend.interface.SubmissionFailure( exception=e )
        if not m or 0 != rc:
            if 0 != rc:
                L.error( '`%s\' exited with code %d; stderr:\n%s'%(
                    self.cfg['execs.condorSubmit'],
                    rc, err) )
            if not m:
                L.error( 'Unable to parse output from %s; stdout:\n%s'%(
                    self.cfg['execs.condorSubmit'], out) )
            raise lamia.backend.interface.SubmissionFailure(
                    output={ 'stdout' : out
                           , 'stderr' : err
                           , 'rc' : rc })
        sdDct = dict(m.groupdict())
        jidBgn, jidEnd = sdDct['JIDRngBgn'].split('.'), sdDct['JIDRngEnd'].split('.')
        jidBgn = [int(a) for a in jidBgn]
        jidEnd = [int(a) for a in jidEnd]
        if jidBgn == jidEnd:
            ret = { 'jID' : jidBgn }
            L.info( 'Single HTCondor job submitted:'
                ' ClusterID=%d, ProcID=%d.'%(jidBgn[0], jidBgn[1]) )
        else:
            ret = { 'jID' : [jidBgn, jidEnd] }
            L.info( 'Multiple HTCondor jobs submitted: %d.%d - %d.%d.'%(
                jidBgn[0], jidBgn[1], jidEnd[0], jidEnd[1] ) )
        return ret, cad

    def dump_logs_for(self, jID, popenKwargs={}):
        pass

    def get_status(self, jID, popenKwargs={}):
        pass

    def kill_job(self, jID, popenKwargs={}):
        pass

    def list_jobs( self
                 , timeout=30
                 , backendArguments=[]
                 , popenKwargs={} ):
        #  $ condor_q -nobatch
        # 
        #
        #-- Schedd: bigbird12.cern.ch : <137.138.120.116:9618?... @ 10/20/18 18:17:27
        # ID        OWNER            SUBMITTED     RUN_TIME ST PRI SIZE CMD
        #794402.0   rdusaev        10/20 18:15   0+00:00:00 I  0    0.0 one.sh foo bar
        #794402.1   rdusaev        10/20 18:15   0+00:00:00 I  0    0.0 one.sh foo bar
        #794402.2   rdusaev        10/20 18:15   0+00:00:00 I  0    0.0 one.sh foo bar
        #794402.3   rdusaev        10/20 18:15   0+00:00:00 I  0    0.0 one.sh foo bar
        #794402.4   rdusaev        10/20 18:15   0+00:00:00 I  0    0.0 one.sh foo bar
        #
        #5 jobs; 0 completed, 0 removed, 5 idle, 0 running, 0 held, 0 suspended
        ##
        # $ condor_q -nobatch
        #
        #
        #-- Schedd: bigbird12.cern.ch : <137.138.120.116:9618?... @ 10/20/18 18:18:26
        # ID        OWNER            SUBMITTED     RUN_TIME ST PRI SIZE CMD
        #794402.1   rdusaev        10/20 18:15   0+00:00:21 R  0    0.0 one.sh foo bar
        #794402.2   rdusaev        10/20 18:15   0+00:00:21 R  0    0.0 one.sh foo bar
        #
        #2 jobs; 0 completed, 0 removed, 0 idle, 2 running, 0 held, 0 suspended
        pass

    def wait_for_job( self, jID
                    , nAttempts=0
                    , intervalSecs=60
                    , popenKwargs={}
                    , report=True):
        """
        Utilizes a dedicated util from HTCondor toolset: `condor_wait' to poll
        the user log file from HTCondor in order to freeze execution until
        certain job is done. Note, that waiting process normally will be
        periodically interrupted in order to print the logging message if
        `report' is `True'. When `condor_wait' stops waiting due to time limit,
        it prints "Time expired." string to `stdout' and exit with code 1.
        The util requires HTCondor log to query the status. Hence, we expect it
        be given within the jID dict.
        """
        assert('jID' in jID[0])  # some job identifier tuple must be in dict
        assert('userLog' in jID[1])  # 'userLog' must be in classAd dict
        L = logging.getLogger(__name__)
        nAttempt = 0
        cmd_ = [ self.cfg['execs.condorWait'] ]
        # If interval in secs is set, append with `-wait <nSecs>'. Note, that
        # `condor_wait' will return `1' exit code upon giving up.
        if intervalSecs:
            cmd_ += ['-wait', str(intervalSecs)]
        # ^^^ Signature: $ condor_wait [-wait intervalSecs] logFile [ClusterID.JobID]
        cmd_ += [jID[1]['userLog']]
        # If jID object refers to job array (not a single clusterID.procID), we
        # have to wait for all of them (thus, not specifying this argument at
        # all).
        if type(jID[0]['jID']) is tuple:
            # this is a single job
            cmd_ += ['%d.%d'%(jID[0]['jID'][0], jID[0]['jID'][1])]
        # Form popen() keyword arguments:
        pkw = copy.deepcopy({ 'stdout' : subprocess.PIPE
                            , 'stderr' : subprocess.PIPE
                            , 'universal_newlines' : True })
        pkw.update(popenKwargs)
        while True:
            nAttempt += 1
            p = subprocess.Popen( cmd_, **pkw )
            out, err = p.communicate()
            rc = p.returncode
            if 1 == rc and intervalSecs and 'Time expired.' in out:
                # This is expected.
                if 0 != nAttempts and nAttempt >= nAttempts:
                    L.warning("Exit waiting loop due to number of attemps"
                    " exceed.")
                    break
                if report:
                    L.info( " ..waiting for the job(s) to finish for at"
                    " least %d secs more%s."%(intervalSecs
                    , '' if not nAttempt else '%d/%d'%(nAttempt, nAttempts) ) )
            elif 0 == rc:
                L.info( "  ..done waiting for job(s) to finish." )
                break
            else:
                L.error( "Unexpected results for"
                    " invocation $ %s"%(' '.join(cmd_)))
                raise lamia.backend.interface.SubmissionFailure(
                    output={ 'stdout' : out
                           , 'stderr' : err
                           , 'rc' : rc })


