import json, urllib.request, sys


scenaries = {
    # Simple task with single job
    'simple-single' : [
        # Get task info -> 404
        { '@': ["/simple01", 'GET'], '@@' : None },
        # Creates task
        {
            '@': ["/simple01", 'POST'],
            "typeLabel" : "testing",
            'config' : {}
        },
        # Get task info
        { '@': ["/simple01", 'GET'], '@@' : None },
        # Has to return 404 since job is not yet created
        { '@': ["/simple01/jobs/lonelyJob", 'GET'], '@@' : None },
        # Creates lonely job
        {
            '@': ["/simple01/jobs/lonelyJob", 'POST'],
            # ...
        },
        # Has to return some job details
        { '@': ["/simple01/jobs/lonelyJob", 'GET'], '@@' : None },
        # Creates event about lonely job being started
        {
            '@': ["/simple01/jobs/lonelyJob", 'PATCH'],
            'type' : 'started'
        },
        # Job being running heartbeat message
        {
            '@': ["/simple01/jobs/lonelyJob", 'PATCH'],
            'type' : 'beat'
        },
        # Job done message
        {
            '@': ["/simple01/jobs/lonelyJob", 'PATCH'],
            # No 'exitCode' provided
            'type' : 'terminated'
        },
    ],
    # Simple task with multiple jobs
    'simple-multiple' : [
        # Creates task
        {
            '@': ["/simple02", 'POST'],
            "typeLabel" : "testing",
            'config' : {}
        },
        # Create few jobs
        { '@': ["/simple02/jobs/jobA", 'POST'], },
        { '@': ["/simple02/jobs/jobB", 'POST'], },
        { '@': ["/simple02/jobs/jobC", 'POST'], },
        { '@': ["/simple02/jobs/jobD", 'POST'], },
        # Update jobs: A terminated normally, B failed, C is not terminated,
        # D has never started:
        # - start
        { '@': ["/simple02/jobs/jobA", 'PATCH'], 'type' : 'started' },
        { '@': ["/simple02/jobs/jobB", 'PATCH'], 'type' : 'started' },
        { '@': ["/simple02/jobs/jobC", 'PATCH'], 'type' : 'started' },
        # - progress
        { '@': ["/simple02/jobs/jobA", 'PATCH'], 'type' : 'beat' },
        { '@': ["/simple02/jobs/jobB", 'PATCH'], 'type' : 'beat' },
        { '@': ["/simple02/jobs/jobC", 'PATCH'], 'type' : 'beat' },
        # - terminate
        { '@': ["/simple02/jobs/jobA", 'PATCH'], 'type' : 'terminated', 'exitCode' : 0 },
        { '@': ["/simple02/jobs/jobB", 'PATCH'], 'type' : 'terminated', 'exitCode' : 1 },
    ],
    # `Classic' task with few arrays and jobs
    'mixed' : [
        # Creates task
        {
            '@': ["/mixed01", 'POST'],
            "typeLabel" : "testing",
            'config' : {}
        },
        # Create few jobs and arrays
        { '@': ["/mixed01/jobs/jobA", 'POST'] },
        { '@': ["/mixed01/jobs/jobB", 'POST'] },
        { '@': ["/mixed01/array/arrA", 'POST'], 'nJobs' : 5, 'tolerance' : 3  },
        { '@': ["/mixed01/array/arrB", 'POST'], 'nJobs' : 2 },
        # Usual storyline...
        { '@': ["/mixed01/jobs/jobA", 'PATCH'], 'type' : 'started' },
        { '@': ["/mixed01/jobs/jobA", 'PATCH'], 'type' : 'beat' },

        { '@': ["/mixed01/arrays/arrB/2", 'PATCH'], 'type' : 'started' },
        { '@': ["/mixed01/jobs/jobB", 'PATCH'], 'type' : 'started' },

        { '@': ["/mixed01/jobs/jobA", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/jobs/jobB", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrB/2", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrB/1", 'PATCH'], 'type' : 'started' },
        { '@': ["/mixed01/arrays/arrB/1", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrA/1", 'PATCH'], 'type' : 'started' },
        { '@': ["/mixed01/arrays/arrB/1", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrB/2", 'PATCH'], 'type' : 'terminated', 'exitCode': 0 },
        { '@': ["/mixed01/arrays/arrA/2", 'PATCH'], 'type' : 'started' },
        { '@': ["/mixed01/arrays/arrA/3", 'PATCH'], 'type' : 'started' },
        { '@': ["/mixed01/arrays/arrA/4", 'PATCH'], 'type' : 'started' },
        { '@': ["/mixed01/jobs/jobA", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrA/5", 'PATCH'], 'type' : 'started' },
        { '@': ["/mixed01/arrays/arrA/1", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrA/2", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrA/3", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrA/1", 'PATCH'], 'type' : 'terminated', 'exitCode' : 1 },
        { '@': ["/mixed01/arrays/arrA/4", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrA/5", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrA/2", 'PATCH'], 'type' : 'terminated', 'exitCode' : 0 },
        { '@': ["/mixed01/arrays/arrA/3", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrA/4", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrA/4", 'PATCH'], 'type' : 'terminated', 'exitCode' : 0 },
        { '@': ["/mixed01/arrays/arrA/5", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrA/5", 'PATCH'], 'type' : 'terminated', 'exitCode' : 0 },
        # We now have 3 of 5 jobs in array A being sucessfully evaluated.
        # Despite one job from array (#1) has been failed, any beat of #3 job
        # will bring back a special indication of this fact. Basing on this
        # indication, client may stop the evaluation of job #3:
        { '@': ["/mixed01/arrays/arrA/3", 'PATCH'], 'type' : 'beat' },
        { '@': ["/mixed01/arrays/arrA/3", 'PATCH'], 'type' : 'beat' },
        # No exit code, meaning that client has interrupted the job
        { '@': ["/mixed01/arrays/arrA/5", 'PATCH'], 'type' : 'terminated' },

        { '@': ["/mixed01/jobs/jobA", 'PATCH'], 'type' : 'terminated', 'exitCode' : 0 },
        { '@': ["/mixed01/jobs/jobB", 'PATCH'], 'type' : 'terminated', 'exitCode' : 0 },
    ]
}

def do_request(addr, rqBody, rqType):
    req = urllib.request.Request(addr, method=rqType)
    req.add_header('Content-Type', 'application/json')
    try:
        if rqBody:
            rsp = urllib.request.urlopen(req, json.dumps(rqBody).encode('utf8'))
        else:
            rsp = urllib.request.urlopen(req)
    except urllib.error.HTTPError as e:
        rsp = e
    print('{rqType: >7} {code} <- {body}'.format(rqType=rqType,
        code=rsp.status, body=rsp.read().decode()), end='')

for s in scenaries[sys.argv[1]]:
    addr, rqType = s.pop('@')
    addr = 'http://127.0.0.1:5000/api/v0{}'.format(addr)
    if '@@' not in s:
        s.update({'!meta' : {
                'time' : '1546632760.271140872',
                'host' : 'localhost'
            }})
        do_request( addr, s, rqType=rqType )
    else:
        do_request( addr, None, rqType=rqType )

