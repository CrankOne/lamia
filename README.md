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
conditioning of the workflow dependencies. At the same time systems like
[PanDA](pandawms.org) and [Pegasus](https://pegasus.isi.edu/)
appears to be a way overencumbered and too complicated for fast prototyping
purposes.

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

It is not yet an alternative to versatile systems like PanDA or Pegasus, but
yet doing things close enough to accompany some initial development with
volatile configuration which has to be translated into shell scenarios and
configuration files in a somewhat flexible way.

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
it requires us to utilize a special linker what is almost never possible for
real-word scientific collaborations of the small and middle scale.

These software usually heavily relies on some kind of preliminary-defined file
structures and higly-volatile configs/text files, etc. The Lamia offers a
generalized way to provide dynamic execution context for them by customizing
the local filesystem subtree with templated approach which is close to what
averaged scientific developer usually does.

# Concepts

Bare minima implies nothing more than just deploying a set of text files on the
certain shared filesystem location and submitting a task to HPC batch back-end.
The "set of files in certain place" implies rendering the _text template files_
w.r.t. to some _context_. _Back-end_ in other hand is not obligatory
interconnected to template rendering procedure, though usually might be
accomplished at the same stage (batch-scheduling communication is frequently
based on text file configs).

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

