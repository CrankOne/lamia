.. Lamia documentation master file, created by
   sphinx-quickstart on Sat Aug 31 11:35:06 2019.
   You can adapt this file completely to your liking, but it should at least
   contain the root `toctree` directive.

Concepts
========

The primary purpose of Lamia is to deploy a set of text files on the
certain filesystem location. The idea behind this project is that these tasks
might be efficiently expressed using some kind of inheritance
(`DRY principle`_: task corresponding to a Python class must implement a
specific interface.

.. _DRY principle: https://en.wikipedia.org/wiki/Don%27t_repeat_yourself

Optionally one may further submit a task described by the filesystem subtree to
HPC batch *back-end*. The "set of files in certain place" implies rendering the
*text template files* (completely defined by user: shell script, ``.JSON``,
``.YAML``, ``libcon[fig]``, etc.) w.r.t. to some *context*. *Back-end*, in
other hand is not obligatory interconnected to template rendering procedure,
though usually might be accomplished at the same stage (batch-scheduling
communication is frequently based on text file configs).

Filesystem
----------

The *file structure manifest* is usually declared in a form of YAML documents,
where keys expected to be in a special form. These keys are sometimes template
string upon which the Lamia computes Cartesian product to infer exact names for
file structure.

.. toctree::
   :maxdepth: 2

   filesystem

Context
-------

While traversing the filesystem, the *context* dictionaries (template
environment w.r.t. which templates are rendered) is evolving in LIFO way: by
coming into templated directory, the stack of runtime environment dictionaries
is overriden with value used for the path substitution.

Templates
---------

Template-rendering utils are based on Jinja2_ package.
Once running, Lamia tools collect the templates located in pre-defined
directories. These templates then are usually referred within the *file
structure manifest* describing the deployment environment of particular tasks.

.. _Jinja2: http://jinja.pocoo.org

.. .. mdinclude:: ../../README.md

Indices and tables
==================

* :ref:`genindex`
* :ref:`modindex`
* :ref:`search`
