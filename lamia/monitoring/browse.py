import argparse
import requests
import os
import json

class MonitoringRequest_0(object):
    def __init__(self, host, port=80):
        self._host = host
        self._port = port

    def dest(self, path=None):
        base = f'http://{self._host}:{self._port}/api/v0'
        if not path:
            return base
        else:
            return os.path.join(base, path)

    def get(self, path=None, expectedStatusCode=200):
        fullPath = self.dest(path=path)
        r = requests.get(fullPath)  # TODO: auth?
        if expectedStatusCode is not None and expectedStatusCode != r.status_code:
            sys.stderr.write( f'GET request "{fullPath}" returned "{r.status_code}".' )
            # ... TODO: other details here?
        return r.json()

    def get_tasks(self):
        return self.get()

    def print_tasks(self, keys=None, asJSON=False, stream=None):
        ts = get_tasks()
        if stream is None: stream = sys.stdout
        if asJSON:
            stream.write(json.dumps(ts, sort_keys=True, indent=2))
        if keys is None:
            keys = [('name', 32), ('username', 12), ('submittedAt', 32), ('comment', None)]
        for t in self.get_tasks():
            pass
            # ... TODO

def main():
    """
    A Lamia command line monitoring browsing tool.
    """
    #if 'list' == sys.argv[1]: ...
    mr = MonitoringRequest_0( host='na58-dev', port=8088 )
    for t in mr.get_tasks():
        t.pop('config')
        print(json.dumps(t, sort_keys=True, indent=2))

if __name__ == "__main__":
    main()

