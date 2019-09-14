RESTful API for Process Monitoring
==================================

The API itself is build around `Task` object. Under the `Task` instance there
should be at least one instance of the remote process or array of the remote
processes. Task may be provided with serialized and compressed `networkx` graph
instance and arbitrary JSON object referring task configuration information.
Neither the `networkx` graph, nor the config object play role in the Lamia's
API and were reserved in ORM as data most frequently used by the extensions.
Using of graph and config data is optional, thus any collision in user code
issued by `networkx` graph mismatch with the task's fields (jobs and arrays)
must be resolved in a favor of the ORM.

The monitoring API keeps track then on individual jobs or job arrays,
storing their history in database. Working processes emits short
`PATCH` requests to incrementaly update the history of particular process.

RESTful API slighly differs from what the ORM declares: each `PATCH` request
updating particular process' info creates new `orm.Event` instance. There is
no direct interface to retrieve these instances then. Instead, their data
will accompany the `GET` response of the job's resource page (so ORM's `Event`
instance does not correspond to any resource).

The `Task`, `Job` and `JobArray` are the subjects of extending. Lamia declares
only basic API.

Extendign RESTful API
---------------------

TODO


