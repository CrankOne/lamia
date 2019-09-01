# -*- coding: utf-8 -*-
# Copyright (c) 2018 Renat R. Dusaev <crank@qcrypt.org>
# Author: Renat R. Dusaev <crank@qcrypt.org>
# 
# Permission is hereby granted, free of charge, to any person obtaining a copy of
# this software and associated documentation files (the "Software"), to deal in
# the Software without restriction, including without limitation the rights to
# use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of
# the Software, and to permit persons to whom the Software is furnished to do so,
# subject to the following conditions:
# 
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
# 
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS
# FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
# COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER
# IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN
# CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""
Lamia provides rudimentary support for monitoring of the running processes via
RESTful API. This module declares object relational model for running tasks.

Three classes below defines the general ORM: Task, Array and Process.

For multiple unique constrain, see:
    https://stackoverflow.com/questions/10059345/sqlalchemy-unique-across-multiple-columns
"""

import datetime, enum, itertools, json, enum
import base64, bz2, pickle  # for dependency graph

from lamia.monitoring.app import db

import sqlalchemy.schema
from sqlalchemy.ext.declarative import DeclarativeMeta

class Task(db.Model):
    """
    A task representation: contains references to arrays of processes and
    individual processes running within a single task context.
    """
    __tablename__ = 'tasks'
    # Unique label of the particular task
    name = db.Column(db.String, primary_key=True)
    #id = db.Column(db.Integer, primary_key=True)
    # Task type tag, optional
    taskClass = db.Column(db.String)
    # Task submission time and date
    submittedAt = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Task completion time and data
    completedAt = db.Column(db.DateTime)
    # bz2 compressed, base64-encoded representation of networkx DiGraph
    depGraph = db.Column(db.String)
    # Task config
    config = db.Column(db.String)  # TODO: db.Column(db.JSON) ?
    # List of arrays associated with the task, if any
    #arrays = db.relationship('ProcArray', back_populates='task', cascade='all, delete-orphan')
    # List of individual jobs associated with the task, if any (not included
    # into arrays list)
    processes = db.relationship( "Process"
                                , back_populates='task')

    def get_graph(self):
        """
        Returns an instance of networkx' DiGraph or None.
        """
        pickle.loads(bz2.decompress(base64.b64decode(self.dep_graph))) if self.dep_graph else None

kStandaloneProcess = 0x1
kArrayProcess = 0x3

class Process(db.Model):
    """
    Remote process abstraction.
    """
    __tablename__ = 'processes'
    # If process not within an array: process name
    name = db.Column(db.String, primary_key=True)
    # If process not within an array: owning task ID
    taskID = db.Column(db.String, db.ForeignKey('tasks.name'), primary_key=True)
    task = db.relationship('Task', back_populates='processes')
    # Usually matches the task's submission time
    submittedAt = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Events log, associated to process
    events = db.relationship( 'Event'
                            , back_populates='process')
    # Polymorphic id
    kin = db.Column(db.Integer)
    __mapper_args__ = {
        'polymorphic_on': kin,
        'polymorphic_identity': kStandaloneProcess
    }
    #__table_args__ = (sqlalchemy.schema.UniqueConstraint( 'taskID', 'name'
    #                                                    , name='_task_name_uc'),)

class Array(Process):
    """
    Multiple physical processes may be unified within one processes array. The
    additional property of this model is fault tolerance: number of the
    processes within the array that might end up with failure but the array
    has to be still considered as successfull.
    """
    __tablename__ = 'arrays'
    name = db.Column(db.String, primary_key=True)
    taskID = db.Column(db.String, primary_key=True)
    # Number of jobs within job array (shall match the length of `processes')
    nJobs = db.Column(db.Integer, nullable=False)
    # Might not be set, indicating no failure tolerance here
    fTolerance = db.Column(db.Integer, nullable=True)
    __mapper_args__ = { 'polymorphic_identity': kArrayProcess }
    __table_args__ = (sqlalchemy.schema.ForeignKeyConstraint([name, taskID],
                                                             [Process.name, Process.taskID]),
                      {})

class Event(db.Model):
    """
    Reflects the process' event. May be one of the following types:
        - Submitted: corresponds to process being sent to the computational
        back-end (HTCondor, LSF, etc). May not be created (?).
        - Started: process started computation
        - Beat: process notifies us that it is still running
        - Terminated: process done its job (successfully or not)
    Events may bear some arbitrary payload for custom usage.
    The submitted/started event carries only the timestamp.
    """
    __tablename__ = 'events'
    # Event ID
    id = db.Column(db.Integer, primary_key=True)
    # Event sent time (self-signed by event)
    sentAt = db.Column(db.DateTime)
    # Event received time
    receivedAt = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Event content (if any)
    payload = db.Column(db.String)  # TODO: db.Column(db.JSON) ?
    # Event class string
    eventClass = db.Column(db.String)
    # If associated process is an array, this column denotes the particular
    # number of the physical process inside the array
    procNumInArray = db.Column(db.Integer)
    #
    process = db.relationship( 'Process'
                             , back_populates='events')
    procID = db.Column(db.String)
    taskID = db.Column(db.String)
    __table_args__ = (sqlalchemy.schema.ForeignKeyConstraint([procID, taskID],
                                                             [Process.name, Process.taskID]),
                      {})

    #__mapper_args__ = {
    #    'polymorphic_on': eventClass,
    #    'polymorphic_identity': 'common'
    #}

