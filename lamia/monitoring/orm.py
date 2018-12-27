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
"""

import datetime
#from sqlalchemy import create_engine, Column, Integer, DateTime, ForeignKey, String
#from sqlalchemy.orm import relationship, sessionmaker
#from sqlalchemy.ext.declarative import declarative_base

from lamia.monitoring.app import db

# See: https://gehrcke.de/2015/05/in-memory-sqlite-database-and-flask-a-threading-trap/
#engine = create_engine('sqlite:///:memory:', echo=True)
#engine = create_engine('sqlite:////tmp/some.sqlite3', echo=True)
#Session = sessionmaker(bind=engine)

class BatchTask(db.Model):
    """
    A task representation: contains references to arrays of processes and
    individual processes running within a single task context.
    """
    __tablename__ = 'tasks'
    id = db.Column(db.Integer, primary_key=True)
    label = db.Column(db.String, unique=True, nullable=False)
    submitted = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    arrays = db.relationship('ProcArray', back_populates='task')
    jobs = db.relationship("RemoteProcess", back_populates='task')
    #type : [alignment|mDST|...],
    #state : [active|done|failed],
    #depGraph : { ... },
    #state : { ... }
    # ...

class ProcArray(db.Model):
    """
    Multiple processes may be unified within one processes array. The
    additional property of this model is fault tolerance: number of the
    processes within the array that might end up with failure but the array
    has to be still considered as successfull.
    """
    __tablename__ = 'arrays'
    id = db.Column(db.Integer, primary_key=True)
    # Usually matches the task's submission time
    submitted = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Number of jobs within job array (shall match the length of `processes')
    nJobs = db.Column(db.Integer, nullable=False)
    # Array name (non-uniq)
    name = db.Column(db.String)
    # Might not be set, indicating no failure tolerance here
    fTolerance = db.Column(db.Integer, nullable=True)

    #
    task = db.relationship('BatchTask', back_populates='arrays')
    # Task to which this array is attached
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    # Processes within the array
    processes = db.relationship("RemoteProcess", back_populates='array')

    # ...

class RemoteProcess(db.Model):
    """
    Remote process representation.
    """
    __tablename__ = 'processes'
    id = db.Column(db.Integer, primary_key=True)
    # Usually matches the task's submission time
    submitted = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # ... events
    # Return code on exit
    rc = db.Column(db.Integer, default=0)

    #
    array = db.relationship('ProcArray', back_populates='processes')
    # If process within an array: parent array's id, if any
    array_id = db.Column(db.Integer, db.ForeignKey('arrays.id'))
    # If process within an array: job index (number in array)
    job_num = db.Column(db.Integer)

    #
    task = db.relationship('BatchTask', back_populates='jobs')
    # If process not within an array: owning task ID
    task_id = db.Column(db.Integer, db.ForeignKey('tasks.id'))
    # If process not within an array: process name
    name = db.Column(db.String)

    #
    events = db.relationship('ProcessEvent', back_populates='process')
    # ...

class ProcessEvent(db.Model):
    """
    Reflects the process' event. May be one of the following types:
        - Submitted: corresponds to process being sent to the computational
        back-end (HTCondor, LSF, etc). May not be created (?).
        - Started: process started computation
        - Beat: process notifies us that it is still running
        - Terminated: process done its job (successfully or not)
    Events may bear some arbitrary payload for custom usage.
    """
    __tablename__ = 'events'
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime, default=datetime.datetime.utcnow)

    #
    process = db.relationship('RemoteProcess', back_populates='events')
    proc_id = db.Column(db.Integer, db.ForeignKey('processes.id'))
    # payload = Column(String)
    # ...

#

#Base.metadata.create_all(engine)

