Filesystem Manifest
===================

Imagine a typical batch task that has to perform few iterations until the final
result is done. From one iteration to another only subtle amount of information
in configuration files changes. Proper way to perform this would be to retrieve
the configuration for particular iteration from network-accessible key-value
pair or somewhat similar.

Practically, people prefer to steer such procedures with configuration files on
network storage that, despite of being a bit reduntant, has benefits of being
easily readable.

.. code-block::

    $ tree /mnt/network-share/my_batch_task/
    /mnt/network-share/my_batch_task/
    ├── iteration-1
    │   └── config.cfg
    ├── iteration-2
    │   └── config.cfg
    └── iteration-3
        └── config.cfg

    3 directories, 3 files

Despite rendering of template text documents themselves is usually
strightforward, there is an ingredient that may significantly simplify the job:
template must be provided with access to current file path semantics
(i.e. number of iteration in example). So, how to impose this information?

Basic Idea
----------

The Lamia proposes to introduce additional templating level: the filesystem
tree template. It is naturally expressed with .YAML document syntax with keys
provided in a special form:

.. code-block:: yaml

    %YAML 1.1
    ---
    root:
        "iteration-{iterNo}":
            "!config.cfg": config.cfg.template
    ...

The exclamation sign there is to make a distinction between files and
directories. Then, if the context for rendering such a template becomes is a
Python dictionary of form:

.. code-block:: python

    { "iterNo" : [1, 2, 3] }

it will be rendered into file structure defined at the beginning. You may then
rely on the environment variable ``iterNo`` in ``config.cfg.template`` file
template -- for ``iteration-1/config.cfg``, ``iteration-2/config.cfg``,
``iteration-2/config.cfg`` this variable becomes ``1``, ``2``, and ``3``
respectively.

Naming Files and Dirs in Manifest
---------------------------------

The key of filesystem manifest entry has to follow this rules:

1. If entry corresponds to a file, exclamation sign (``!``) has to precede the
   string.
2. Name itself is a Python `format_map()`_ template string -- a subject of
   *path template substitution*.
3. Optionally, the key may be have a suffix starting with ``@`` sign. This
   suffix is then may be referenced by other templates via *path template
   rendering context* in order to reference this particular file path.

I.e. the key part may be summarized as ``[!]<name>[@alias]``.

.. _format_map(): https://docs.python.org/3/library/stdtypes.html#str.format_map

File Attributes
---------------

The value part of the entry is expected to be either a ``null``, string, or
object. For directories ``null`` corresponds to empty dir, for files the
``null`` value means it has to be reserved for alias-only entries (ones that
will be referred by templates but not physically created to the time of
template rendering).

String values for dir-entry has no semantics and causes an exception while for
files string value refers to the table (i.e. it is a shortened form of ``id``
attribute, see below).

If entry is a file (i.e. has an exclamation mark), the following attributes may
be provided:

* ``id`` refers to the template file to be rendered
* ``mode`` is the octal code of POSIX filesystem permissions
* ``contextHooks`` is a list of strings that correspond to special functions
  loading additional context data for particular template rendering. E.g. when
  this additional data may lead to significant overhead or destructively
  mutates context data.
* ``conditions`` is a list of strings containing Python code prefixed by
  ``eval:`` that conditionally enables rendering of template depending on
  current path context.

Examples
--------

Imaginary example of the filestructure for following jobs sequence:

1. Make shell scripts and config files for N iterations of some imaginary
   ``glorbonicate`` process
2. After everything is done, use ``summarize.sh`` script that will generate
   some summary output into ``summary/`` dir.


.. code-block:: yaml

    version: 0.1
    "glorb-{datetime}@baseDir":
        "iteration-{iterNo}":
            "!glorb.cfg@configFile": glorb.cfg.template
            "!glorbonicate.sh@glorbExec":
                id: glorb.sh.template
                mode: 0755
        "!summarize.sh@summarizeExec":
            id: generate-summary.sh.template
            mode: 0755
        "summary@outputDir": null

Running it on *path context*

.. code-block:: python

    { "iterNo" : [1, 2] }

leads to

.. code-block::

    $ tree glorb-1568445909
    glorb-1568445909
    ├── iteration-1
    │   ├── glorb.cfg
    │   └── glorbonicate.sh
    ├── iteration-2
    │   ├── glorb.cfg
    │   └── glorbonicate.sh
    ├── summarize.sh
    └── summary

    3 directories, 5 files

The templates of ``glorb.cfg`` and ``glorbonicate.sh`` files have an access
to ``iterNo`` variable and may, thus gain benefit of changing context.

.. todo:: It would be a nice feature that the ``summary.sh.template`` must
    have an access to path template  substitution results produced by
    sequential applying of the ``iterNo`` list to this structure. We consider
    using sorted tuple as template keys for substitution results, e.g.
    ``configFile[iterNo=1]`` or similar.

    Currently, this functionality achieved by ``contextHooks`` callbacks.

