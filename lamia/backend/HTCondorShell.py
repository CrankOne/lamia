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
import logging, re, os, copy, subprocess, itertools, networkx, functools, io \
     , hashlib, base64, pickle, bz2
import sys  # XXX
# uncomment this and few lines below for @native-graph-drawing
#import pylab
# uncomment this and few lines below for @graphviz-graph-drawing
#from networkx.drawing.nx_agraph import graphviz_layout, to_agraph
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
                'should_transfer_files' : 'NO'
                #'when_to_transfer_output' : 'ON_EXIT'
            }
        }
    }

# Example output of condor_submit_dag:
#   -----------------------------------------------------------------------
#   File for submitting this DAG to HTCondor           : alignment/P04phys2/exec/alignment.dag.condor.sub
#   Log of DAGMan debugging messages                 : alignment/P04phys2/exec/alignment.dag.dagman.out
#   Log of HTCondor library output                     : alignment/P04phys2/exec/alignment.dag.lib.out
#   Log of HTCondor library error messages             : alignment/P04phys2/exec/alignment.dag.lib.err
#   Log of the life of condor_dagman itself          : alignment/P04phys2/exec/alignment.dag.dagman.log
#   
#   Submitting job(s).
#   1 job(s) submitted to cluster 951223.
#   -----------------------------------------------------------------------
rxHTCondorDAGOutParLine = re.compile( r'^(?P<description>.+)\s+:\s(?P<value>.+)$'
                                    , re.MULTILINE)

def serialize_queue( qd, nProc ):
    """
    Returns HTCondor's `queue ...' string and number of parallel processes
    per single homogeneous product.
    """
    L = logging.getLogger(__name__)
    rxItem = re.compile(r'\$\((?P<name>Item\d+)\)')
    if qd is None:
        return "queue %d"%nProc, 1
    # items multiline list
    imlk, imlv = [], []
    for k in qd.keys():
        m = rxItem.match(k)
        if m:
            imlk.append(m.groupdict()['name'])
        imlv.append( qd[k] )
    argsLines = []
    try:
        for cmb in itertools.product(*imlv):
            argsLines.append(' '.join(cmb))
    except:
        L.error('..while computding product on %s'%str(imlv))
        raise
    return "queue %d %s from (\n%s\n)"%( nProc
                                       , ','.join(imlk)
                                       , '\n'.join(argsLines) ), len(argsLines)

class HTCondorShellSubmission(lamia.backend.interface.Submission):
    """
    An HTCondor job submission representation.
    Ctr composes arguments for `condor_submit' shell invocation.
    """
    @staticmethod
    def macros( submissionTag=None ):
        r = { 'jIndex' : '$(Process)'
            , 'jID' : '$(Cluster).$(Process)' }
        if submissionTag:
            r['subTag'] = submissionTag
        else:
            r['subTag'] = 'single'
        return r

    def _mk_subm_classAd( self, nProcs, cad, submissionTag=None
            , jobName=None  # used only if monitoringAPI isn't None
            , monitoringAPI=None ):
        L = logging.getLogger(__name__)
        # NOTE: the native `classad' module's instances seems to be pretty
        # useless due to their rudimentary serialization mechanism. Writing the
        # submission file ad-hoc seems to be a better alternative since ClassAd
        # syntax is pretty straightforward, even what is concerned `queue'
        # keyword.
        cad["executable"] = self.tCmd[0]  #os.path.abspath( self.tCmd[0] )
        dn, fexec = os.path.split(self.tCmd[0])
        # Put the submission file nearby of exec, if it is not supplied by
        # back-end arguments
        if 'submissionFile' not in self.condorSubmitArgs:
            postfix = '.htcondor.sub'
            if submissionTag:
                # use submission tag to produce different submission files
                postfix = '.%s%s'%(submissionTag, postfix)
            submissionFilePath = os.path.join( dn, fexec + postfix)
        else:
            submissionFilePath = self.condorSubmitArgs.pop('submissionFile') \
                    .format(**self.macros(submissionTag))
        # Put the user-log file nearby of exec, if it is not supplied by
        # back-end arguments
        if 'userLog' not in self.condorSubmitArgs:
            postfix = '.htcondor-log'
            if submissionTag:
                postfix = '.%s%s'%(submissionTag, postfix)
            cad["userLog"] = os.path.join( dn, fexec + postfix)
        else:
            cad["userLog"] = self.condorSubmitArgs.pop('userLog') \
                    .format(**self.macros(submissionTag))
        self.userLog = cad['userLog']  # Save this value for further usage
        #
        if 'environment' in cad:
            assert(type(cad['environment'] is dict))
            if 'HTCONDOR_JOBINDEX' in cad['environment']:
                L.error( "The `HTCONDOR_JOBINDEX' specified for the"
                        " environment will be overriden." )
        else:
            cad['environment'] = {}
        cad['environment']['HTCONDOR_JOBINDEX'] = '$(Process)' \
                                            if self.nProcs else 'SINGLE'
        # Append environment with event URI variable.
        if monitoringAPI:
            if 'JOB_EVENT_ADDR' in cad:
                L.error( "The `JOB_EVENT_ADDR' specified for the environment"
                        " will be overriden." )
            cad['environment']['JOB_EVENT_ADDR'] = monitoringAPI.job_event_address( jobName
                    , '$(Process)' if self.nProcs > 1 or self.isImplicitArray else None )
            L.info( 'Monitoring endpoint (JOB_EVENT_ADDR environment variable)'
                   + ' for job "%s" will be set'%jobName
                   + ' to "%s"'%cad['environment']['JOB_EVENT_ADDR'] )
        if len(self.tCmd) > 1:
            if not self.isImplicitArray:
                cad["arguments"] = self.tCmd[1:]
                nProcs = self.nProcs
            else:
                cad["arguments"], cad['queue'] = \
                        lamia.backend.interface.inject_placeholders(
                                self.tCmd[1:], placeholderFormat="$(Item%d)" )
        # backendArguments['classAd']
        if os.path.isfile(submissionFilePath):
            # Warn user about re-writing the existing submission file. It is
            # generally not a worrisome error since we kind of expect this to
            # happen with re-generation of the same deployment, but have no
            # means to control it using the standard subtree deployment
            # procedure. In case of iterative tasks, however, this error may
            # indicate an absent `submissionFile' parameter.
            L.warning( 'HTCondor submission file "%s" exists'
                    ' and will be overwritten.'%submissionFilePath )
        with open(submissionFilePath, 'w') as f:
            for k, v in cad.items():
                if 'queue' == k:
                    continue  # syntax differs for queue
                if type(v) is list \
                or type(v) is tuple:
                    strV = ' '.join(v)
                elif type(v) in (int, float, str):
                    strV = str(v)
                elif type(v) is dict:
                    # we escape the double quotes here (acc. to
                    # `man condor_submit' it has been done with double-quotes (""))
                    # see also:
                    #   https://research.cs.wisc.edu/htcondor/manual/v7.8/condor_submit.html#76968
                    # for reference.
                    strV = '"%s"'%(' '.join(['%s=%s'%(k, vv.replace('"', '""')) \
                                                for k, vv in v.items()]))
                else:
                    raise TypeError('Can not serialize type `%s\' into classAd'
                        ' file.'%type(v).__name__ )
                f.write( '%s = %s\n'%(k, strV) )
            qs, self._nImplicitJobs = serialize_queue(cad.get('queue', None), nProcs)
            f.write(qs)
        return submissionFilePath

    #def __hash__(self):
    #    return id(self)

    def __init__( self, jobName, cfg
                , cmd=None
                , nProcs=1
                , stdout=None, stderr=None
                , timeout=300
                , submissionTag=None
                , backendArguments={}
                , popenKwargs={}
                , monitoringAPI=None ):
        L = logging.getLogger(__name__)
        self.condorSubmitExec = cfg['execs.condorSubmit']
        self.condorSubmitArgs = copy.deepcopy(cfg['condorSubmit'])
        self.condorSubmitArgs.update(backendArguments)
        for k in ['queue', 'terse', 'batch-name', 'output', 'error']:
            v = self.condorSubmitArgs.pop(k, None)
            if v:
                L.warning( '"-%s"%s argument to HTCondor\'s submission exec'
                        ' will be ignored in favor of one defined'
                        ' programmatically, by back-end instance.'%(k,
                            '="%s"'%str(v) if v else '') )
        super().__init__(jobName, cmd, nProcs)
        baseAd = copy.deepcopy( cfg['classAds.submit'] )
        baseAd.update({
                'output' : stdout.format(**self.macros()),
                'error' : stderr.format(**self.macros()),
            })
        self.submissionFilePath = self._mk_subm_classAd( nProcs, baseAd
                , submissionTag=submissionTag
                , monitoringAPI=monitoringAPI
                , jobName=jobName )
        self.cmd = [ cfg['execs.condorSubmit'], self.submissionFilePath
               , '-terse'
               , '-batch-name', jobName
               ]
        self.pkw = copy.deepcopy({ 'stdout' : subprocess.PIPE
                                 , 'stderr' : subprocess.PIPE
                                 , 'universal_newlines' : True })
        self.pkw.update(popenKwargs)

class HTCondorShellBackend(lamia.backend.interface.BatchBackend):
    """
    The batch-processing back-end implementation for HTCondor.
    Relies on manually-written ClassAd files and shell utilities.
    """

    def backend_type():
        return 'HTCondorShell'

    def _submit( self, j ):
        L = logging.getLogger(__name__)
        try:
            L.debug("Supplementary popen() arguments: %s."%str(j.pkw) )
            L.debug("Submission command: $ %s"%(' '.join(j.cmd)))
            submJob = subprocess.Popen(j.cmd, **j.pkw)
            out, err = submJob.communicate( timeout=self.cfg['timeouts.condorSubmit'] )
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
        if hasattr( j, 'userLog') and j.userLog:
            ret['userLog'] = j.userLog
        else:
            L.warning('Job submission have no "userLog" attribute.')
        return ret

    def __init__(self, config, monitoringAPI=None):
        super().__init__(config, monitoringAPI=monitoringAPI)

    def queue(self, jobName, **kwargs):
        """
        Submit the job to HTCondor
        Will forward `cmd' as a string within the `subprocess.Popen'.

        Important `backendArguments' entry is a "submissionFile" that shall
        denote a file where corresponding submission classAd will be generated.
        If it is not provided, the first `cmd' entry will be considered as a
        filename to which we append a `.sub' postfix and use resulting path for
        generating a submission file.
        """
        return HTCondorShellSubmission( jobName, self.cfg, monitoringAPI=self.monitoringAPI, **kwargs )

    def dispatch_jobs(self, js, DAGFilePath=None):
        L = logging.getLogger(__name__)
        if isinstance(js, HTCondorShellSubmission):
            if not js.dependencies:
                # Trivial case -- no dependencies => no additional operations
                # needed, straigtforward submission.
                rs = self._submit( js )
                if self.monitoringAPI:
                    self.monitoringAPI.follow_task(js)
                return rs
            js = [js]
        # Hereafter use networkx to build the DAG (which then will be rendered
        # into HTCondor's DAGMan file).
        def _dep_convolution(acc, b):
            acc.update(b.depGraph)
            return acc
        G = functools.reduce( _dep_convolution, [networkx.DiGraph()] + list(js) )
        #
        dagf = io.StringIO()
        for j in G:
            dagf.write( 'JOB {jobName} {submFile}\n'.format(
                jobName=j.jobName, submFile=j.submissionFilePath ) )
        for j in G:
            if not list(G.successors(j)): continue
            dagf.write( 'PARENT %s CHILD '%j.jobName )
            dagf.write( ' '.join(dep.jobName for dep in G.successors(j)) )
            dagf.write('\n')
        #
        if not DAGFilePath:
            if 'DAGFilesDir' not in self.cfg:
                raise RuntimeError('No parameter for "DAGFilesDir" found in'
                        ' HTCondorShell config, nor the "DAGFilePath" keyword'
                        ' argument provided with dispatch_job() invocation.')
            tok = base64.b64encode(hashlib.sha1(
                dagf.getvalue().encode()).digest()).decode().strip('=')
            DAGFilePath = os.path.join(self.cfg['DAGFilesDir'], tok + '.dag')
        # @native-graph-drawing
        #networkx.draw(G, with_labels=True)
        #pylab.savefig('/tmp/DAG.png')
        # @graphviz-graph-drawing
        #A = to_agraph(G)
        #A.layout('dot')
        #A.draw('/tmp/DAG-2.png')
        # _________
        # TODO: we're done with main part and now are going to notify the
        # monitoring server with job being submitted. Code below is highly
        # experimental: we write pickled representation of the dependency
        # graph and encode it into base64 to be then sent to the monitoring
        # server:
        #if self.monitoringAPI:
        #    dgpckl = io.BytesIO()
        #    networkx.write_gpickle(G, dgpckl)
        #    ##pickle.dump( G, dgpckl )
        #    #with open( './xxx.base64', 'w' ) as f:
        #    #    f.write(base64.b64encode(bz2.compress(dgpckl.getvalue())).decode())
        #    #assert(False)  # XXX
        #    self.monitoringAPI[''] = ...
        # _________
        with open(DAGFilePath, 'w') as f:
            f.write(dagf.getvalue())
        sCmd = [self.cfg['execs']['submitDAG'], '-force', DAGFilePath]
        try:
            submJob = subprocess.Popen( sCmd, stdout=subprocess.PIPE
                                            , stderr=subprocess.PIPE )
            out, err = submJob.communicate( timeout=self.cfg['timeouts.condorSubmit'] )
            rc = submJob.returncode
        except Exception as e:
            raise lamia.backend.interface.SubmissionFailure( exception=e )
        if 0 != rc:
            L.error("`%s' exited with code %d; stderr:\n%s"%(
                ' '.join(sCmd), rc, err.decode() ))
        else:
            if err:
                L.warning("`%s' stderr message(s):\n%s"%(
                    ' '.join(sCmd), err.decode()))
            if self.monitoringAPI:
                self.monitoringAPI.follow_task(js)
        ret = { 'out' : [] }
        for m in rxHTCondorDAGOutParLine.finditer( out.decode() ):
            ret['out'].append( m.groupdict() )
        ret['stderr'] = err.decode()
        ret['rc'] = rc
        for m in re.finditer( r'^(?P<nJobs>\d+) job\(s\) submitted to cluster (?P<clusterID>\d+)\.'
                            , out.decode(), re.MULTILINE ):
            assert( 'nJobs' not in ret.keys() )  # must be a single line in stdout
            ret.update( m.groupdict() )
        return ret

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
        assert('jID' in jID)  # some job identifier tuple must be in dict
        assert('userLog' in jID)  # 'userLog' must be in classAd dict
        L = logging.getLogger(__name__)
        nAttempt = 0
        cmd_ = [ self.cfg['execs.condorWait'] ]
        # If interval in secs is set, append with `-wait <nSecs>'. Note, that
        # `condor_wait' will return `1' exit code upon giving up.
        if intervalSecs:
            cmd_ += ['-wait', str(intervalSecs)]
        # ^^^ Signature: $ condor_wait [-wait intervalSecs] logFile [ClusterID.JobID]
        cmd_ += [jID['userLog']]
        # If jID object refers to job array (not a single clusterID.procID), we
        # have to wait for all of them (thus, not specifying this argument at
        # all).
        if type(jID['jID']) in (tuple, list):
            # this is a single job
            cmd_ += ['%d.%d'%(jID['jID'][0], jID['jID'][1])]
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
                    , '' if not nAttempt else ' (%d/%d)'%(nAttempt, nAttempts)))
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


