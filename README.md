# The Lamia Project

This project was initially a dedicated supplement for the procedure of physics
alignment in NA58 (COMPASS) experiment. Despite it still has a single purpose,
the architectural features are kept being general allowing one to design
additional modules and blueprints for the core functions that are:

   * Flexible and high-parameterized generating of templated scripts, option
   files and binary artifacts within complex file structures.
   * Utilizing such a file structures within the HTC/HPC context
   (LSF/HTCondor) for the batch processing purposes.
   * Monitoring the computations on the task-specific semantics on web:
   integration ELK stack, extracting of task-specifica information, journaling,
   cataloguing, etc.
   * Rudimentary HTC/HPC steering support

As for 2018, only the alignment procedure for NA58 (COMPASS) CERN is used as a
major use case and development-driving task. However it is planned to move the
generic parts of the Lamia (core, WUI, etc) into a dedicated standalone
repository.

