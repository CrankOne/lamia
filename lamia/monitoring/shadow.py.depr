#!/usr/bin/env python
"""
A wrapper script performing subprocess invokation with realtime blocking
capture of generated output. Intended usage is as a lightweight wrapper helping
to adapt applications for Lamia monitoring system unobtrusively (without
modifying the user application code itself).

Process lifecycle:
    * When started will immediately submit the STARTED event to monitoring
service.
    * When stdout/stderr yields the string matching the -c,--capture regular
expression(s), the HEARTBEAT event will be sent to monitoring service, bearing
the payload.
    * When target process is done, the TERMINATED event will be sent to
monitoring service, keeping its return code.

The STARTED and BEAT responses may bring the "no-need" flag, upon which the
script will interrupt the evaluation (unless -i,--insist flag is set).

In case when host pointed by -a,--out-addr is not available, or when there
are no active service, the script will become darmant, meaning no events will
be issued. It will then quietly exit once the target process is done.

NOTE: consider prefixing command `stdbuf -oL` in order to force line-based
bufferization of target commands.
"""

from __future__ import print_function
import sys, argparse, re, subprocess, socket, copy, datetime, requests, json
from six.moves import urllib
from Queue import Queue
from threading import Thread

#                           * * *   * * *   * * *
# This script may produce some diagnostic messages. This string will be used
# as as a common prefix for them.
gOwnPrefix = '\033[1mSHADOW WRAPPER MSG\033[0m: '

#                           * * *   * * *   * * *
# Message disatching function
def send_lamia_request(addr, rqBody_, rqType, auth=None):
    """
    Sends the request of given type returning the response as dict. The addr
    is substituted as is into corresponding (pointed by rqType) function of
    `requests' library. Optional auth parameter may refer to simple HTTP
    authentication.
    """
    #req = urllib.request.Request(addr, method=rqType)
    #req.add_header('Content-Type', 'application/json')
    # For requests with body (like POST), apend the content with '!meta' field
    # typically consumed by Lamia.
    if rqBody_:
        rqBody = copy.copy(rqBody_)
        rqBody['!meta'] = {
                'time' : datetime.datetime.now().strftime('%s.%f'),
                'host' : socket.gethostname()
            }
    else:
        rqBody = None
    # Submit request with method given by rqType string, with, or without
    # request body.
    rq_fn = getattr(requests, rqType)
    if rqBody is not None:
        rq = rq_fn( addr, json=rqBody, auth=auth )
    else:
        rq = rq_fn( addr, auth=auth )
    try:
        jsDat = rq.json()
    except Exception as e:
        jsDat = None
    return rq.status_code, jsDat

#                           * * *   * * *   * * *
# API v.0 (dev test)
class LamiaMonitoringAPI0(object):
    """
    Class producing reentrant object for simple communication with Lamia
    monitoring RESTful API.

    For the 0 API version, all events communication is performed through the
    single address, with various request methods.
    """
    def __init__( self, addr, port
                , taskLabel
                , jobID
                , persistantTask=False
                , auth=None ):
        self.dest = 'http://{addr}:{port}/api/v0/{taskLabel}/{jobID}'.format(
                addr=addr, port=port, taskLabel=taskLabel,
                jobID=(jobID if type(jobID) is str else '{}/{}'.format(*jobID) ) )
        self.persistantTask = persistantTask
        self.auth=None
        self.serviceAvailable = True

    def _do_proceed(self, data):
        """
        Determines, whether task has to proceed. Will return False ONLY if
        server returned data with field `keepGoing' AND this field is set to
        `False'.
        """
        if self.persistantTask:
            return True
        keepGoing = True
        if type(data) is dict and 'keepGoing' in data:
            keepGoing = data['keepGoing']
        return keepGoing

    def _dispatch_event(self, *args, **kwargs):
        """
        Depending on whether `self.serviceAvailable' is true will either send
        an event data by forwarding args,kwargs to `send_lamia_request()', or
        do nothing.
        """
        if self.serviceAvailable:
            try:
                return send_lamia_request( self.dest, *args, **kwargs )
            except requests.exceptions.ConnectionError as e:
                sys.stderr.write( "%sMonitoring service %s is not available: \"%s\""
                        " Unable to dispatch events!\n"%( gOwnPrefix, self.dest
                                                        , str(e) ) )
                self.serviceAvailable = False
            except Exception as e:
                sys.stderr.write( "%sException thrown during attempt to reach"
                        " the monitoring service at %s: \"%s\". Falling back"
                        " to darmant state.\n"%( gOwnPrefix, self.dest, str(e) ) )
                self.serviceAvailable = False
        return 0, None

    def started(self, payload=None):
        """
        Emits the STARTED event.
        """
        dct = {'type' : 'started'}
        if payload: dct['payload'] = payload
        rc, respData = self._dispatch_event( dct, 'patch', auth=self.auth )
        if 201 != rc:
            sys.stderr.write('Unable to initialized job object. Request'
                    ' return code: %d.'%rc)
            if respData:
                sys.stderr.write( json.dumps(respData, indent=2) )
        return rc, respData, self._do_proceed(respData)

    def beat(self, payload=None):
        """
        Emits the HEARTBEAT event.
        """
        dct = {'type' : 'beat'}
        if payload: dct['payload'] = payload
        rc, respData = self._dispatch_event( self.dest, dct, 'patch', auth=self.auth )
        return rc, respData, self._do_proceed(respData)

    def terminated(self, rc, payload=None):
        """
        Emits the TERMINATED event.
        """
        dct = {'type' : 'terminated', 'exitCode' : rc}
        if payload: dct['payload'] = payload
        return self._dispatch_event( self.dest, dct, 'patch', auth=self.auth )

    def dump_cfg(self):
        return {
                'apiVersion' : "0",
                'commonHTTPPrefix' : self.dest,
                'isPersistent' : self.persistantTask,
                'auth' : self.auth
            }

#                           * * *   * * *   * * *
# Command line argument parser
p = argparse.ArgumentParser( description=__doc__
                           , formatter_class=argparse.RawTextHelpFormatter
                           , epilog='For further reading see the full'
                           ' package\'s docs at:\n\thttps://github.com/CrankOne/lamia\n'
                           'Distributed under MIT license.')
p.add_argument( '-a', '--address'
              , help='Lamia monitoring service address with port.'
              , required=True )
p.add_argument( '-t', '--task'
              , help='Name of the task used by monitoring API to identify batch'
              ' tasks.'
              , required=True )
p.add_argument( '-s', '--signature'
              , help='Signature of this remote process for Lamia monitoring'
              ' service. Shall be either a string denoting standalone jobs:'
              ' <processName> or <arrayName>:<jobNo> signing the jobs array'
              ' process.'
              , required=True )
p.add_argument( '--api-ver'
              , help='Lamia REST API version to use.'
              , default='0' )
p.add_argument( '-i', '--insist'
              , help='When set, ignore the "no need" recommendation from'
              ' monitoring service.'
              , action='store_true')
p.add_argument( '-E', '--use-stderr'
              , help='Use stderr for capture instead of stdout.'
              , action='store_true')
p.add_argument( '-c', '--capture'
              , help='A regular expression for the output to capture. If regex'
              ' has group "completion", it will be used as numerical denotion'
              ' of progress passed by.' )
p.add_argument( '-o', '--stdout'
              , help='Redirect target process stdout to.'
              , required=True )
p.add_argument( '-e', '--stderr'
              , help='Redirect target process stderr to.'
              , required=True )
p.add_argument( '--auth'
              , help='File with authentication information (user password)'
              ' for plain HTTP auth.' )
p.add_argument( '--own-prefix'
              , help='Sets the common prefix used to identify own script'
              ' messages.', default=gOwnPrefix )

p.add_argument('shCmd', nargs=argparse.REMAINDER)

#                           * * *   * * *   * * *
# Threaded function performing stream capture
def reader(pipe, queue):
    try:
        with pipe:
            for line in iter(pipe.readline, b''):
                queue.put((pipe, line))
    finally:
        queue.put(None)

#                           * * *   * * *   * * *
# Entry point
def main(args):
    gOwnPrefix = args.own_prefix
    # Validate presence of user app to run.
    if not len(args.shCmd):
        sys.stderr.write( '%serror -- no child process argument were given.\n'%gOwnPrefix )
        return 1
    # Extract the host/port from `addr'
    gd = re.search( r'(?:http.*://)?(?P<host>[^:/ ]+).?(?P<port>[0-9]*).*'
                  , args.address ).groupdict()
    host, port = gd['host'], gd['port']
    # Parse the job signature to use
    jobSignature = args.signature if ':' not in args.signature else tuple(args.signature.split(':'))
    # Obtain authentication information, if given
    if args.auth:
        raise NotImplementedError()  # TODO: parse auth file
    else:
        authData={}
    # Instantiate Lamia API
    if '0' == args.api_ver:
        api = LamiaMonitoringAPI0( host, port, args.task, jobSignature
                                 , args.insist, authData )
    else:
        raise NotImplementedError('API of version {} is not supported.'%args.api_ver)
    # Dump application config
    print(json.dumps(api.dump_cfg(), indent=2))
    # Initialze subprocess instance, readers and queue for parallel acquizition
    q = Queue()
    p = subprocess.Popen( args.shCmd
                        , stdout=subprocess.PIPE
                        , stderr=subprocess.PIPE )
    tO, tE = Thread( target=reader, args=[p.stdout, q] ) \
           , Thread( target=reader, args=[p.stderr, q] )
    # Run the stuff
    tO.start()
    tE.start()
    rc, dat, doProceed = api.started()
    for _ in range(2):
        for src, line in iter(q.get, None):
            if src == p.stdout:
                sys.stdout.write( line )
            elif src == p.stderr:
                sys.stderr.write( line )
            else:
                raise RuntimeError('Bad file descriptor in queue: %s'%src)
            # Once the message satisfies the catch-condition, do the capture:
            # ...
    api.terminated( p.returncode )

#                           * * *   * * *   * * *
# Run
if "__main__" == __name__:
    sys.exit(main(p.parse_args()))
