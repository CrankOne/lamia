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

## Running in Development Mode

To get the running development server on localhost with sqlite database stored
at `/tmp/lamia-restful-test.sqlite3` do:

    $ FLASK_DEBUG=1 FLASK_APP=lamia.monitoring.app flask run

To check basic communication using `curl` do:

    $ lamia/tests/curl_post_monit.sh

console log will depict basic ideas behind the interaction with API.
