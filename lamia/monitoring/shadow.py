#!/usr/bin/env python
"""
A wrapper script performing subprocess invokation with realtime blocking
capture of generated output. Intended use is as a lightweight wrapper helping
to adapt applications for Lamia monitoring system.

Process lifecycle:
    * When started will immediately submit the STARTED event to monitoring
service.
    * When stdout/stderr yields the string matching the -c,--capture regular
expression(s), the HEARTBEAT event will be sent to monitoring service.
    * When target process is done, the TERMINATED event will be sent to
monitoring service, keeping its return code.

The STARTED and BEAT responses may bring the "no-need" flag, upon which the
script will interrupt the evaluation (unless -i,--insist flag is set).

In case when host pointed by -a,--out-addr is not available, or when there
are no active service, the script will become darmant, meaning no events will
be issued. It will quietly die once the target process is done.

NOTE: consider prefixing command `stdbuf -oL` in order to force line-based
bufferization of target commands.
"""

from __future__ import print_function
import sys, argparse, re, subprocess, socket, copy, datetime, requests, json

def send_lamia_request(addr, rqBody_, rqType, auth=None):
    """
    Sends the request of given type returning the response as dict. The addr
    is substituted as is into corresponding (pointed by rqType) function of
    `requests' library. Optional auth parameter may refer to simple HTTP
    authentication.
    """
    req = urllib.request.Request(addr, method=rqType)
    req.add_header('Content-Type', 'application/json')
    if rqBody_:
        rqBody = copy.copy(rqBody_)
        rqBody['!meta'] = {
                'time' : datetime.datetime.now().strftime('%s.%f'),
                'host' : socket.gethostname()
            }
    else:
        rqBody = None
    rq_fn = getattr(requests, rqType)
    if rqBody is not None:
        rq = rq_fn( addr, json=rqBody, auth=auth )
    else:
        rq = rq_fn( addr, auth=auth )
    return rq.status_code, rq.json()

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
        self.dest = 'http://{addr}:{port}/api/0/{taskLabel}/{jobID}'.format(
                addr=addr, port=port, taskLabel=taskLabel,
                jobID=(jobID if type(jobID) is str else '{}/{}'.format(*jobID) ) )
        self.persistantTask = persistantTask
        self.auth=None

    def _do_proceed(self, data):
        """
        Determines, whether task has to proceed. Will return False ONLY if
        server returned data with field `keepGoing' AND this field is set to
        `False'.
        """
        if self.persistantTask:
            return True
        keepGoing = True
        if 'keepGoing' in data:
            keepGoing = data['keepGoing']
        return keepGoing

    def started(self, payload=None):
        """
        Emits the STARTED event.
        """
        dct = {'type' : 'started'}
        if payload: dct['payload'] = payload
        rc, respData = send_lamia_request( self.dest, dct, 'patch', auth=self.auth )
        return rc, respData, self._do_proceed(respData)

    def beat(self, payload=None):
        """
        Emits the HEARTBEAT event.
        """
        dct = {'type' : 'beat'}
        if payload: dct['payload'] = payload
        rc, respData = send_lamia_request( self.dest, dct, 'patch', auth=self.auth )
        return rc, respData, self._do_proceed(respData)

    def terminated(self, rc, payload=None):
        """
        Emits the TERMINATED event.
        """
        dct = {'type' : 'terminated', 'exitCode' : rc}
        if payload: dct['payload'] = payload
        return send_lamia_request( self.dest, dct, 'patch', auth=self.auth )

    def dump_cfg(self):
        return {
                'apiVersion' : "0",
                'commonHTTPPrefix' : self.dest,
                'isPersistent' : self.persistantTask,
                'auth' : self.auth
            }

# Global flag indicating the script state. When set to False, no outern
# connections will be issued.
gActive = True

#
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
              , help='File with authentication information (user\\npassword)'
              'for plain HTTP auth.' )

p.add_argument('shCmd', nargs=argparse.REMAINDER)

#
# Entry point
def main(args):
    if not len(args.shCmd):
        sys.stderr.write( 'ERROR: No child process argument were given.\n' )
        return 1
    gd = re.search( r'(?:http.*://)?(?P<host>[^:/ ]+).?(?P<port>[0-9]*).*'
                  , args.address ).groupdict()
    host, port = gd['host'], gd['port']
    jobSignature = args.signature if ':' not in args.signature else tuple(args.signature.split(':'))
    if args.auth:
        raise NotImplementedError()  # TODO
    else:
        authData={}
    if '0' == args.api_ver:
        api = LamiaMonitoringAPI0( host, port, args.task, jobSignature
                                 , args.insist, authData )
    else:
        raise ValueError('API of version {} is not supported.'%args.api_ver)
    print(json.dumps(api.dump_cfg()))
    #
    #
    #p = subprocess.Popen( shCmd, stdout=stdStream, stderr=errStream )
    #for line in iter(p.stdout.readline, b''):
    #    line = p.stdout.readline()
    #    if '' == line and process.poll() is not None:

#
# Run
if "__main__" == __name__:
    sys.exit(main(p.parse_args()))
