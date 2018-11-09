# The Lamia Project

This project was initially a dedicated supplement for the procedure of physics
alignment in NA58 (COMPASS) experiment. Despite it still has a single purpose,
the architectural features are kept being general allowing one to design
additional modules for the core functions that are:

   * Flexible and high-parameterized generating of templated scripts, option
   files and binary artifacts within complex file structures.
   * Utilizing such a file structures within the HTC/HPC context
   (LSF/HTCondor) for the batch processing purposes.
   * Rudimentary HTC/HPC steering support
   * Monitoring the computations on the task-specific semantics on web:
   integration ELK stack, extracting of task-specifica information, journaling,
   cataloguing, etc.

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


# Templates

...

# Filesystem

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
(TODO: shall we? custom filter have to be enough)

