# Lamia Monitoring Facility

Lamia introduces a simple
[RESTful API](https://en.wikipedia.org/wiki/Representational_state_transfer)
for monitoring on the running jobs. This API is built around the "task" object
in a way each resource refers to the owning task instance by its unique name.

It is implemented using [Flask](https://github.com/pallets/flask),
[flask-restful](https://flask-restful.readthedocs.io/en/latest/),
[sqlalchemy](https://www.sqlalchemy.org/) and
[marshmallow](https://marshmallow.readthedocs.io/en/stable/).

Currently, no front-end is shipped with the Lamia project itself.

## ORM

Entities:

* `Task` class represents a set of jobs and job arrays. No dependencies
information is imposed at the level of DB -- task owns its jobs in simple
one-to-many relationship. Some additional information like submission date and
time or the configuration (as plain string object) is stored in the table.
* `Process` represents a running remote process.
* `Array` extend `Process` with number of jobs information.
* `Event` is owned by `Process` class in one-to-many relationship. Events bears
submission date, arbitrary payload string and special string column named
`eventClass` that is supposed to reflect the process' state.

Traits:

* Each task may refer to array(s) and individual remote process(es) besides
its own data
* The difference between the remote process (job) within the array and running
standalone is the way of addressing: in the array one must refer to array name
and job number, for the single jobs only its name is needed.
* Each remote process representation refers to the list of "events" that bring
meaningful information about remote process lifecycle.

The lifecycle of remote process is pretty strightforward:

1. Submitted
2. Started
3. Running (issues "beat" events from time to time)
4. Termination

We do not rely on the process mandatory issuing any message except for its
termination (but user API may). The termination event is used in some
pre-defined search queries to determine whether the job, array or entire task
sucessfully finished its evaluation.

## REST Requests Semantics

Methods usually have the following semantics:

 | Resource       | `/cars/12`                  | `/cars`                   |
 |----------------|-----------------------------|---------------------------|
 | GET (read)     | Returns a specific car      | Returns a list of cars    |
 | POST (create)  | Creates new car with ID     | Bulk creation of cars     |
 | PUT (create)   | Edit of car with ID         | Bulk edition of cars      |
 | PATCH (update) | Update of single car        | Bulk updates of cars      |
 | DELETE         | Deletes a specific car      | Bulk deletion of cars     |

The difference between `POST`/`PUT`/`PATCH` accepted within the current version
of api (v. 0.0):

* The `POST` method is proposed as a generic request type for creation of
the items, often involving intrinsic transformation of the input.
* The `PUT` method is deisgned for internal usage only as it does direct
modification of the resource with no side effects.
* The `PATCH` method implicitly creates a new entities in DB corresponding to
update brought by `PATCH` request.

## Notes on the "Progress" messages

Process may optionally submit `PROGRESS` message(s) via POST. The request
JSON's body may (must?) provide integer value named "progress" describing
current progress estimate. Estimate of overall process or job measure is
varying depending on whether the *thresholdProgress* of owning process is set.

1. When neither process' threshold is set, nor the job's eventbring any value
in `PROGRESS` messages, no job progress or solitary process estimation is
available rather than its status indication. The array process' progress is
estimated by fraction of processes marked as `DONE`.
2. When process' threshold is not set but `PROGRESS` event bring some non-zero
values in their `progress` field, this field is interpreted as percentage
value (0-100) of individual job. For solitary processes the lates `PROGRESS`
estimation will define full progress of process, while for array processes,
it is estimated as sum of individual job's persentegaes divided by overall
percentage progress.
3. When no process threshold is set and `PROGRESS` events bring no `progress`
value, the threshold is considered as number of jobs within the array needed
to be `DONE` in order to complete the process. This case makes no sense for
solitary processes. Individual job progress is not available. Overall (array)
process progress is calculated then as the ratio of `DONE` jobs to process'
threshold. Once required number `DONE` jobs within the array will be reached,
the monitoring server will provide additional information for the responses
indicating that further evaluation for the jobs is no more needed.
4. When both, the processes' `threshold` and job event's `progress` are set,
the 

 |   #| Process' thresh | Event progress | Job progress       | Process progress | 
 |----|-----------------|----------------|--------------------|------------------|
 |   1| not set         | not set        | (not avail.)       | num of DONE jobs |
 |   3| not set         | set            | perc. expected     | overall perc.    |
 | 2,4| set             | not set        | (not avail.)       | num of DONE jobs |
 |   5| set             | set            | Unnormed estimate  | overall perc.    |

The PROGRESS "payload" may bring arbitrary content.

Use cases:
1. Bunch of opaque processes, no way to customize sources in order to impose
cURL code reporting progress to the Lamia monitoring service.
2. Parallel randomized calculus till some result is found among one of the
processes.
3. Track individual progress of jobs: threshold is not set, events bring
normalized payload (<=100); example: analysis of certain data set
where each job is performing own specific task -- building a certain histogram.
4. Process certain number of jobs: threshold is set, events bring no info on
their progress (competitive evaluation); example: ASAP calculus.
5. Process certain number of entries overall: threshold is set to absolute
value, events bring (unnormalized) number of processed entries (example:
process certain number of physical events).

*Warning*: client code must consider that process' progress estimation may be
above 100% since jobs do not immediately react (and may not react at all,
depending on their implementation) on the progress reached the threshold.

## Running in Development Mode

To get the running development server on localhost with sqlite database stored
at `/tmp/lamia-restful-test.sqlite3` do:

    $ FLASK_DEBUG=1 FLASK_APP=lamia.monitoring.app flask run

xxx:

    $ FLASK_ENV=DEVELOPMENT FLASK_DEBUG=1 python -m lamia.monitoring.app lamia.www/rest-srv.yaml

To check basic communication using `curl` do:

    $ lamia/tests/curl_post_monit.sh

console log will depict basic ideas behind the interaction with API.

## Running on Servers

Proposed approach to run Lamia monitoring server is to use Waitress here.
To accomplish running on production, consider the following stages on
RHEL-family distro:

### Testing

1. Make a directory for the Lamia monitoring:

    $ sudo mkdir -p /var/src/lamia.www
    $ cd /var/src/lamia.www

2. Deploy and activate Python virtual environment for the project:

    $ python3 -m venv
    $ source venv/bin/activate

3. Fetch and install the Lamia sources into virtualenv:

    $ git clone git@github.com:CrankOne/lamia.git lamia.src
    $ pip install -e lamia.src

4. Copy and edit the configuration file for the monitoring server:

    # cp lamia.src/assets/configs/rest-srv.yaml .
    # nano rest-srv.yaml

5. Copy and edit the systemd's unit for the monitoring server:

    # cp lamia.src/assets/configs/service /etc/systemd/system/lamia-monitoring.service
    # nano /etc/systemd/system/lamia-monitoring.service

6. Recache systmd units and start the Lamia monitoring servide:

    # systemctl daemon-reload
    # service lamia-monitoring start

Check the unit's status with:

    # systemctl status lamia-monitoring

7. In case of troubles, the Lamia monitoring server's logs are available:

    # joutnalctl -u lamia-monitoring
    # journalctl _PID=2263  # (use pid provided by status)
    # tail /var/log/lamia/error.log

### Basic Idea for Production

1. Make a virtual environment for the Lamia to run somewhere. Do not forget to
provide the virtual environment or system python installation with modules
necessary for your preferable database back-end.

2. Create a system (no home, no login, etc.) user called, e.g. `lamiasrv`:

    # useradd -r lamiasrv

3. Assemble the binary distribution package from sources with

    $ python setup.py bdist_wheel

and copy the package file (named like `lamia_templates-0.1.0-py3-none-any.whl`)
to production host if need.

4. Create directory for logging and change owner to newly-created user:

    # mkdir /var/log/lamia
    # chown lamiasrv:lamiasrv /var/log/lamia

5. Copy and/or edit the `share/lamia/rest-srv.yaml` config w.r.t. to logging
directories, preferred database back-end, etc.

6. Edit the `share/lamia/service` file w.r.t. to virtual environment location,
lamia config, user. Copy it to `/etc/systemd/system/lamia-monitoring.service`

