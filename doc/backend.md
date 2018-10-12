# Guidelines for back-end developers

For the "back-end" we imply the particular computation infrastructure software
that provides batch-processing facility. The examples are:
[IBM LSF](https://www.ibm.com/support/knowledgecenter/en/SSETD4/product_welcome_platform_lsf.html)
and [HTCondor](https://research.cs.wisc.edu/htcondor/).

## Interface

In order to integrate the back-end one have to implement the
`lamia.backend.interface.BatchBackend` class. Few method of this interfacing
class are used by Lamia's task to perform batch processing routines.

The idea of the back-end interface is to provide bare minimum for most of the
task in a way that user code (tasks) does no need to know of a particular
back-end implementation. I.e. we summarize most of the common task with a
unified set of commands:

* A name of the back-end to provide run-time instantiation and basic
querying of available back-ends (`backend_type()` abstract property).
* A submission (`submit()`) routine requiring one to specify:
   1. the text label (job name),
   2. the target files for logging (redirected `stdin`/`stdoit` output).
   3. Some back-end-specific arguments, if needed
   4. The timeout for sub-shell invocation (if appliable)
   5. The Python's `popen()` supplementary args (if appliable)
* Job querying routine (`get_status()`)
* Job interruption routine (`kill_job()`)
* A special routine freezing the execution until job stops (`wait_for_job()`)
* A routine, retrieving `stdout`/`stderr` logs of an active job
* Jobs listing method (`list_jobs()`).

Note, that even if some interfacing methods aren't yet implemented, some tasks
might be still able to perform their doings. Please, consider putting a stub
`raise NotImplementedError()` within the method. Though, we have consider it
a must to implement all of them up to some time...

