# The Lamia Project

The solely purpose of the Lamia project is to accompany the batch-scheduling
back-ends (like IBM LSF or HTCondor) by introducing additional interface
offering extended abilities for configuration.

The practical need of such an extension comes from the fact that most of our
scientific software does not support versatile enough configuration mechanisms
that might be easily integrated with existing batch-scheduling solutions like
[Luigi](https://luigi.readthedocs.io/en/stable/index.html),
[Airflow](https://airflow.apache.org/), [Oozie](http://oozie.apache.org/), or
[Azkaban](http://data.linkedin.com/opensource/azkaban). This projects
were designed to simplify the scheduling and their focus lies on the
conditioning of the workflow dependencies.

Contrary, Lamia focuses more on the creation of _supporting environment_ for
the individual batch jobs and tasks with well-known and rigid workflows:

   * Flexible and high-parameterized generating of templated scripts, option
   files and binary artifacts within complex file structures.
   * Utilizing such a file structures within the HTC/HPC context
   (LSF/HTCondor) for the batch processing purposes.
   * Rudimentary HTC/HPC steering support
   * Monitoring the computations on the task-specific semantics on web:
   integration ELK stack, extracting of task-specific information, journaling,
   cataloguing, etc.

Since the project is yet on pretty early stage of development, no online
documentation offered here so far, unfortunately.

# History and features

This project was initially a dedicated supplement for the procedure of physics
alignment in NA58 (COMPASS) experiment. Despite it still has a single purpose,
the architectural features are general enough to allow one to design additional
modules for the core functions.

As for 2018, only the alignment-related procedures for NA58 (COMPASS) CERN is
used as a major use case and development-driving task. However it is planned to
move the generic parts of the Lamia (core, WUI, etc) into a dedicated standalone
repository.

## Rationale

Despite any bright intentions most of the real scientific software projects are
quite far from the those standards the batch computing facilities where
dedicated to. Considering software architecture and most UNIX conventions as
what one can name as "software purism", most of the practical developments
sticks for quick'n'dirty solutions leading to increasing technical debt and
messing with the implications batch processing facilities were initially
developed for. E.g. the HTCondor's Universes plethora becomes pointless because
it requires us to utilize a special linker what is almost never possible.

These software usually heavily relies on some kind of preliminary-defined file
structures and higly-volatile configs/text files, etc. The Lamia offers a
generalized way to provide dynamic execution context for them by customizing
the local filesystem subtree with templated approach.

# Concepts

We've tried to introduce very few concepts to the stage in order to keep things
clear.

## Templates

Template-rendering utils are based on [Jinja2](http://jinja.pocoo.org) package.
Once running, Lamia tools collect the templates located in pre-defined
directories. These templates then are usually referred within the _file
structure manifest_ describing the deployment environment of particular tasks.

## Filesystem

The _file structure manifest_ is usually declared in a form of YAML documents,
where keys expected to be in a special form. These keys are sometimes template
string upon which the Lamia computes cartesian product to defer exact names for
file structure.

## Monitoring API

Lamia introduces a simple RESTful API for monitoring of the running jobs. The
API is built around the "task" object in a way each resource refers to the
owning task instance by its unique name.

### ORM

Simplified relation between principle entities are depicted on the diagram.
Traits:

* Each task may refer to array(s) and individual remote process(es) besides
its own data
* Job arrays is nothing more than named and enumerated set of the remote
processes.
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

## Reserved context definitions

The special variable `LAMIA` defined during context-rendering procedure have
few sections that reflects volatile run-time conditions, specific for
particular file instance:

    * `LAMIA.path` is the path of file currently being rendered
    * `LAMIA.pathContext` is the subset of variables interpolated by path
currently being rendered. For example, if path was `options{iteration}.txt` and
`iteration` was set to `[1, 2, 3]`, the `LAMIA.pathContext.iteration` will
refer to particular value of `{iteration}`: `1` for `options1.txt`, `2` for
`options2.txt`, etc.
    * `LAMIA.subtree` refers to the subtree object being currenlty rendered.
This object is an instance of `lamia.core.filesystem.Paths`. It might be used
to retrieve the aliased paths from within a template rendering context.

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

