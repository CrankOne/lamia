# Testing script that implements a common scenario of batch task with several
# jobs and arrays defined.

HOST=http://localhost:5000

TASK_LABEL=testing-$(printf '%x' $(date +%s))
BASE_URL=$HOST/api/v0/$TASK_LABEL

echo "Base URL: ${BASE_URL}"

echo "CREATING A TASK"
curl --header 'Content-Type: application/json' \
     --request POST --data @- $BASE_URL \
     -w '%{http_code}\n' <<-EOF
	{
	    "_meta" : {
	        "host" : "$(hostname)",
	        "time" : $(date -u +%s.%N)
	    },
	    "depGraph" : "QlpoOTFBWSZTWU/lCzkAFIp////be/r6///L///+J///3+ZhbC8EoJQSAgAsCACQgAkI4AbvnfT7MuoKFPVd2qgHfZ9HhKmqR6nqAA0ZANGgADQ08oaGgAAAAAADQANBo9Ro0Cqm2SjNJvUyIyaMmJo0GBGEyMIxNAaGJgTCMho0MEYIBppiaBkqn7yogiaMgfqjQYCAMgMjI0YjE0AMhpo00yNADRoGgAAIn6lTUAAAAAADQaAAAyABoANANGgABkAGgBFSm9UU9kmI0ExAAA0AAAAHqaAyB6jRoAAAADQAAKkiFPQU09JkzUNEnkT0Taan6UaPRPUxGjQ0ZHigDMoaBtQekaGgADQaHaDYBSK/gAQUoQcx8jOPmbeorGK16zavLm0fMvHSrF+KU2/pjw1JdKd+o70tYlgtLWiKhQUoipQVQWstVBaoRK9yQirR44BIVhH2WhxoEQIgARAiBAsNVgYElsE2nJJ7qp3yAliUIdcZKSGSlFarRWrTRTmin1VqjVUkMlEAwSIB7eWgc8EgHx+AGtrYIqRViuSVcGpJpNtAyrwQB3iSRjA1SHSmpUkkkkkkkkkkk0001uoyMSPQSHUFRVBUFBUFBUVQQWSYiIDauhQexgdMTEkDLJBlcHIxrkwzXIiBiIiBiIiBiIiBiImyB1IoNdOypmRQbyQoMgCBIg2FFFFFFk222222222222222222229AimQQJhM3NO3JuYEE+IEgGeeeeefYhQa4oM6gt0jVG3nBQcPnGWDnoRWGHBZVVUpSYJKqUmOEwTCCyVIYxaXMyBnkGnDAwgV0GZmGZA0AoMhv0TJy0hNkJpvQ8lLNEbLXl08tMcfYZehV8NvSTDpR4Ld5O3vZxno9kN8Ow9VHwZFrJaLaU3478eLzrx1vphu5/LjGIdjZZMaTaltCnJZac90EySL0Su6fMCka1PyWo9YWoYh293uVrnPju+j4u9uY1lWgOnwJCWDi809V4OgkGcALYoNRMmQWe11OD7cqdVJxQaJCi9u74MZrS1ezy/Hjw+f17QpPG13jDjsNoVB0YhWKQl+PNISxeCVDoVITysPWyQdduBNWZpjMtb4/BqDVG5s1aYvngdTLLVNEkLc1ITws9qcXh4fTiGcV5+jyA5gUFPka0gZ0nnECtKvfCgxvYp2KSKtSmkrsUGV+kOUNWOdsgcBlZITG0aA4UhPIre4kNUR+KQ9eHqJVwubQ6gXgXC4NkBTUX0v4ebCSDE6ruqahQYAA7lgCXB0g3Ua6iBGLEFSQmPJezDCxel72l6ve0uq9dMNwOYAC4AuoBW5nLteS/WkP9ianh9fbTFOiCIiIgq+G7gqORO0g53FzWVL3ttwswth6izs2xi9Y42XVe9jNBlJU4lKsClJpJNDzcLgcEiASAY1eNVwXeV89QUx0KhaEWYsWhApba8i1aoiIt8Tin3/WKY/HMjNHIMAwZWET5SQleJbkiIc6v4Y+kuGVJCf3774rtQKmK0T7jNig0OhTKsig4oBRbvTRCg2LMKjVl6+58DQkJh+/C2aQlZ2jf/rytTfg8nPgQcCmlpxVMNUJlUwVQdQhZi/HCTCcfEqXt8AHWzSEvILlaatYFSSOJ38UhOl9vGSE3EhPsVaKUbUtvJCdhIS3RSEw3ktu387hQVOSlUtKtVUqlYLY5bWckVSQlO53a2p/Hi1wVp6vHzduv32yDdFUiqRVIqkVSKYwipJIukJUlkv9em4YNm6gtM4xQb3V9qOqlJvJxpCafG1w8TAGGrLTc1pZLctOVUI7WnndmGfXlWFIX90KnFz+qkJ3t7qDLPO2zmJCbK3EhN/fSE+ywhQd3YoWSddgkgWaADQBbOGHqwORlGVmy1GAXESpJ2Rg0AEfojp8jCIAiQ4rp2b/gBxyjDBDAFCWaNFHC0ARlHkIyzD+7py4+GO6hW+GFkp96nRq3T4cPv29LL3Kyp7sVUYfP5McE9jPLDc/xfXWtKmEf5VS1oqoqoqoqoqkRkFAZjQQbIqgAAAAAAABINmfbGIn/ISoKioqlQ955XW+G9DstF8Q7hzSuwlWvJ4JqGuqSqgv0Q9EPOxxFVCqnDrvdKoVQwqJyu37wenTPPY06baN/HXu5vL5cY0kZSWileym4FJF/0hf6KDjCB/xdyRThQkE/lCzkA==",
	    "tags" : ["testing", "one", "two"],
	    "config" : "some cfg here",
	    "processes" : {
	        "tstArray1" : 10,
	        "tstArray2" : [10, 8],
	        "someJob1" : null
	    }
	}
	EOF

echo "RETRIEVING A TASK INFO"
curl --header 'Content-Type: application/json' \
  --request GET "$BASE_URL" \
  -w '%{http_code}\n'

echo "RETRIEVING A TASK INFO BY NON-EXISTING TAG (NONE)"
curl --header 'Content-Type: application/json' \
  --request GET "$HOST/api/v0?tag=three" \
  -w '%{http_code}\n'

echo "RETRIEVING A TASK INFO BY TAG (ONE)"
curl --header 'Content-Type: application/json' \
  --request GET "$HOST/api/v0?tag=testing&tag=two" \
  -w '%{http_code}\n'

echo "RETRIEVING AN ARRAY JOB INFO"
curl --header 'Content-Type: application/json' \
  --request GET "$BASE_URL/tstArray2?asArray=true" \
  -w '%{http_code}\n'

echo "COMMITING A 'STARTED' EVENT"
curl --header 'Content-Type: application/json' \
  --request POST --data @- "$BASE_URL/tstArray2/event?arrayIndex=3" \
  -w '%{http_code}\n' <<-EOF
	{
	    "eventClass" : "STARTED",
        "payload" : "arbitrary data here",
	    "_meta" : {
	        "host" : "$(hostname)",
	        "time" : "$(date -u +%s.%N)"
	    }
	}
	EOF

echo "COMMITING A 'PROGRESS' EVENT"
curl --header 'Content-Type: application/json' \
  --request POST --data @- "$BASE_URL/tstArray2/event?arrayIndex=3" \
  -w '%{http_code}\n' <<-EOF
	{
	    "eventClass" : "STARTED",
        "payload" : "{\"progress\" : 90}",
	    "_meta" : {
	        "host" : "$(hostname)",
	        "time" : "$(date -u +%s.%N)"
	    }
	}
	EOF

echo "COMMITING A 'STARTED' EVENT FOR SINGLE JOB"
curl --header 'Content-Type: application/json' \
  --request POST --data @- "$BASE_URL/someJob1/event" \
  -w '%{http_code}\n' <<-EOF
	{
	    "eventClass" : "STARTED",
        "payload" : "arbitrary data here",
	    "_meta" : {
	        "host" : "$(hostname)",
	        "time" : "$(date -u +%s.%N)"
	    }
	}
	EOF

echo "COMMITING A 'FINISHED' EVENT FOR SINGLE JOB"
curl --header 'Content-Type: application/json' \
  --request POST --data @- "$BASE_URL/someJob1/event" \
  -w '%{http_code}\n' <<-EOF
	{
	    "eventClass" : "FINISHED",
        "payload" : "arbitrary data here",
	    "_meta" : {
	        "host" : "$(hostname)",
	        "time" : "$(date -u +%s.%N)"
	    }
	}
	EOF

echo "RETRIEVING ALL STARTED JOBS"
curl --header 'Content-Type: application/json' \
  --request GET "$BASE_URL/@all?hasEventsOfClass=STARTED" \
  -w '%{http_code}\n'

#echo "RETRIEVING AN ARRAY JOB INFO"
#curl --header 'Content-Type: application/json' \
#  --request GET "$BASE_URL/tstArray2?isArray=true" \
#  -w '%{http_code}\n'

echo "RETRIEVING AN ARRAY JOB INFO"
curl --header 'Content-Type: application/json' \
  --request GET "$BASE_URL/tstArray2/event?arrayIndex=3" \
  -w '%{http_code}\n'

#echo "DELETING A TASK"
curl --header 'Content-Type: application/json' \
     --request DELETE "$BASE_URL" \
     -w '%{http_code}\n'

