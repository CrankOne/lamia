import json, urllib.request, sys


scenaries = {
    # 0 scenario: single task with lonely job
    'simple' : [
        # Creates task
        {
            '@': ["", 'POST'],
            'label': "simpleTestingTask",
            "typeLabel" : "testing",
            'config' : {}
        },
        # Retrieves a status of jobs/arrays for the task just being created
        # (empty)
        { '@': ["/simpleTestingTask/jobs/lonelyJob", 'GET'], '@@' : None },
        # Creates lonely job
        {
            '@': ["/simpleTestingTask/jobs/lonelyJob", 'POST'],
            # ...
        },
        # Creates event about lonely job being started
        {
            '@': ["/simpleTestingTask/jobs/lonelyJob", 'PUT'],
            'type' : 'started'
        },
        # Job being running heartbeat message
        {
            '@': ["/simpleTestingTask/jobs/lonelyJob", 'PUT'],
            'type' : 'beat'
        },
        # Job done message
        {
            '@': ["/simpleTestingTask/jobs/lonelyJob", 'PUT'],
            'type' : 'terminated'
        },
    ]
}

def do_request(addr, rqBody, rqType):
    req = urllib.request.Request(addr, method=rqType)
    req.add_header('Content-Type', 'application/json')
    rsp = urllib.request.urlopen(req, json.dumps(rqBody).encode('utf8'))
    print('{code} <- {body}'.format(code=rsp.status, body=rsp.read().decode()), end='')

for s in scenaries[sys.argv[1]]:
    addr, rqType = s.pop('@')
    addr = 'http://127.0.0.1:5000/api/v0{}'.format(addr)
    s.update({'!meta' : {
            'time' : '1546632760.271140872',
            'host' : 'localhost'
        }})
    do_request( addr, s, rqType=rqType )

