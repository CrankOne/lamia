# The Lamia Project

The solely purpose of the Lamia project is to accompany the batch-scheduling
back-ends (like IBM LSF or HTCondor) by introducing additional interface
offering extended abilities for configuration.

The practical need of such an extension comes from the fact that most of our
scientific software does not support configuration mechanisms being versatile
enough to integrate with existing batch-scheduling solutions (like
[Luigi](https://luigi.readthedocs.io/en/stable/index.html),
[Airflow](https://airflow.apache.org/), [Oozie](http://oozie.apache.org/), or
[Azkaban](http://data.linkedin.com/opensource/azkaban)). This projects
were designed to simplify the scheduling and their focus lies on the
conditioning of the workflow dependencies rather then configuration of each
particulat job. At the same time systems like [PanDA](pandawms.org) and
[Pegasus WMS](https://pegasus.isi.edu/) appears to be a way overencumbered and
too complicated for fast prototyping purposes.

The Lamia focuses more on the creation of _supporting environment_ for
the individual batch jobs and tasks with well-known and rigid workflows:

   * generating of shell scripts and configuration files within
   complex file structures
   * usage of such file structures by the HTC/HPC context (LSF/HTCondor) for
   the batch processing
   * rudimentary HTC/HPC steering support
   * rudimentary monitoring the computation processes on the task-specific
   semantics on web: integration ELK stack, extracting of task-specific
   information, journaling, cataloguing, etc.

It is not yet an alternative to versatile systems like PanDA or Pegasus, but
yet doing things close enough to accompany some initial development with
volatile configuration which has to be translated into shell scenarios and
configuration files in a somewhat flexible way.

# Project History and Background

This project was initially a dedicated supplement for the procedure of physics
alignment in [NA58 (COMPASS) experiment (CERN)](http://compas.web.cern.ch/).
Despite it had a singular purpose, the architectural features are general
enough to allow one to design additional modules on top of the core functions.
Though, the name "Lamia" still stands for an anagram of the "*ali*gnment
*m*onitoring".

