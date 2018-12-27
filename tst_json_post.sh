HOST=http://localhost:5000

# Creates a testing task (depgraph is taken from one of the alignment tasks)
curl --header 'Content-Type: application/json' \
     --request PUT --data @- $HOST/api/task/new \
     -w '%{http_code}\n' <<EOF
{
    "label" : "testingTask",
    "meta" : {
        "host" : "$(hostname)",
        "time" : "$(date +%s.%N)"
    },
    "depGraph" : "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",
    "config" : { "some" : "thing" },
    "arrays" : {
        "tstArray1" : [10, 20],
        "tstArray2" : 100
    },
    "typeLabel" : "testing",
    "jobs" : [ "someJob1", "someJob2" ]
}
EOF

# Submits a "started" event for one of the arrays' job
curl --header 'Content-Type: application/json' \
  --request POST --data @- $HOST/api/event \
  -w '%{http_code}\n' <<EOF
{
    "from" : ["testingTask", "tstArray1", 12],
    "type" : "started",
    "meta" : {
        "host" : "$(hostname)",
        "time" : "$(date +%s.%N)"
    }
}
EOF

# Submits a "progress" event for one of the arrays' job
#curl --header 'Content-Type: application/json' \
#  --request POST --data @- $HOST/api/event \
#  -w '%{http_code}\n' <<EOF
#{
#    "from" : ["testingTask", "tstArray1", 12],
#    "type" : "beat",
#    "meta" : {
#        "host" : "$(hostname)",
#        "time" : "$(date +%s.%N)"
#    },
#    "payload" : {
#        "completion" : 42
#    }
#}
#EOF

# Searches for the tasks of certain type
curl --header 'Content-Type: application/json' \
  --request POST --data @- $HOST/api/search \
  -w '%{http_code}\n' <<EOF
{
    "meta" : {
        "host" : "$(hostname)",
        "time" : "$(date +%s.%N)"
    },
    "subject" : "task",
    "terms" : {
        "name" : "testing"
    },
    "values" : [ "id" ]
}
EOF

