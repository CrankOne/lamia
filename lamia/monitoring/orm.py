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

import datetime, enum, itertools, json, enum, logging
import base64, bz2, pickle  # for dependency graph

from flask import current_app as app

import sqlalchemy.schema
import flask_sqlalchemy
from sqlalchemy import func, select, and_ #, where
from sqlalchemy.ext.associationproxy import association_proxy
import sqlalchemy.ext.hybrid
from sqlalchemy.ext.declarative import DeclarativeMeta

db = flask_sqlalchemy.SQLAlchemy()

# Table maintainging task-to-tags relationship (many to many).
# TODO: auto-delete tag(s) being no more associated with any task.
tagsAssocTable = db.Table( 'tag_associations'
                         , db.Column('task_name', db.String, db.ForeignKey('tasks.name'))
                         , db.Column('tag_name', db.String, db.ForeignKey('tags.name'))
                         )

class Task(db.Model):
    """
    A task representation: contains references to arrays of processes and
    individual processes running within a single task context.
    """
    __tablename__ = 'tasks'
    # Unique label of the particular task
    name = db.Column(db.String, primary_key=True)
    # User identifier submitted the task
    username = db.Column(db.String)
    # User's e-mail address
    emailNotify = db.Column(db.String)
    # Task comment, if any
    comment = db.Column(db.String)
    # Task submission time and date
    submittedAt = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Submission host IP
    submHostIP = db.Column(db.String)
    # Task submission host IP address
    hostname = db.Column(db.String)
    # bz2 compressed, base64-encoded representation of networkx DiGraph
    depGraph = db.Column(db.String)
    # Task config
    config = db.Column(db.String)  # TODO: db.Column(db.JSON) ?
    # List of individual jobs associated with the task, if any (not included
    # into arrays list)
    processes = db.relationship( "Process"
                                , back_populates='task'
                                , cascade="save-update, merge, delete, delete-orphan" )
    # List of tags associated with task
    tags = db.relationship( 'Tag'
                          , secondary=tagsAssocTable, backref='tasks' )

    def get_graph(self):
        """
        Returns an instance of networkx' DiGraph or None.
        """
        pickle.loads(bz2.decompress(base64.b64decode(self.dep_graph))) if self.dep_graph else None

class Tag(db.Model):
    """
    Classifiers to sort out the tasks.
    """
    __tablename__ = 'tags'
    name = db.Column(db.String, primary_key=True)

kStandaloneProcess = 0x1
kArrayProcess = 0x3

class Process(db.Model):
    """
    Remote process abstraction.
    """
    __tablename__ = 'processes'
    # If process not within an array: process name
    name = db.Column(db.String, primary_key=True)
    # Progress threshold; cumulative progress must be this big before API
    # starts to respond "enough" to the processes
    thresholdProgress = db.Column(db.Integer, nullable=True)
    # If process not within an array: owning task ID
    taskID = db.Column(db.String, db.ForeignKey('tasks.name'), primary_key=True)
    task = db.relationship('Task', back_populates='processes')
    # Events log, associated to process
    events = db.relationship( 'Event'
                            , back_populates='process'
                            , cascade="save-update, merge, delete, delete-orphan"
                            )
    # Polymorphic id
    kin = db.Column(db.Integer)
    __mapper_args__ = {
        'polymorphic_on': kin,
        'polymorphic_identity': kStandaloneProcess,
        #'concrete' : True
    }

    @sqlalchemy.ext.hybrid.hybrid_property
    def lastEventClass(self):
        """
        A computed property reflecting current job status: returns last class.
        """
        L, S = logging.getLogger(__name__), db.session
        lec = S.query(Event.eventClass).filter( and_( Event.taskID == self.taskID
                                              , Event.procID == self.name ) ) \
                .order_by(Event.recievedAt.desc()).first()
        return lec[0] if lec else None

    @sqlalchemy.ext.hybrid.hybrid_property
    def progress(self):
        """
        Returns the overall progress estimation for the process by retrieving
        maximum "progress" value among all the events related to this process.
        """
        L, S = logging.getLogger(__name__), db.session
        return S.query(sqlalchemy.func.max(Event.progress)) \
                 .filter( and_( Event.taskID == self.taskID
                              , Event.procID == self.name )
                        ).scalar()

class Array(Process):
    """
    Multiple physical processes may be unified within one processes array. The
    additional property of this model is fault tolerance: number of the
    processes within the array that might end up with failure but the array
    has to be still considered as successfull.
    The overall progress is also an important indicator allowing one to quench
    processes after some threshold. The progress in case of job arrays has to
    be (usually) estimated as a sum of individual job progress estimations.
    """
    __tablename__ = 'arrays'
    name = db.Column(db.String, primary_key=True)
    taskID = db.Column(db.String, primary_key=True)
    # Number of jobs within job array (shall match the length of `processes')
    nJobs = db.Column(db.Integer, nullable=False)
    # Might not be set, indicating no failure tolerance here
    fTolerance = db.Column(db.Integer, nullable=True)
    #
    __mapper_args__ = { 'polymorphic_identity': kArrayProcess
                      #, 'concrete' : True
                      }
    __table_args__ = (sqlalchemy.schema.ForeignKeyConstraint([name, taskID],
                                                             [Process.name, Process.taskID]),
                      {})

    @sqlalchemy.ext.hybrid.hybrid_property
    def progress(self):
        """
        Computes the overall progress estimate for the array by summing up
        the maximum "progress" values for individual jobs.
        An interesting, but frequent usecase, see for reference:
            https://stackoverflow.com/questions/45775724/sqlalchemy-group-by-and-return-max-date
        """
        L, S = logging.getLogger(__name__), db.session
        subq = S.query( Event.taskID, Event.procID
                      , Event.procNumInArray
                      , sqlalchemy.func.max(Event.progress).label('maxprogr')
                      ).filter( and_( Event.taskID == self.taskID
                                    , Event.procID == self.name )
                                    ) \
                       .group_by(Event.procNumInArray)
        # NOTE: the above subquery may be useful base to see per-job-in-array
        # progress summary, e.g.:
        #for r in subq:  print(r)
        return S.query(sqlalchemy.func.sum(subq.subquery().c.maxprogr)).scalar()

    #@sqlalchemy.ext.hybrid.hybrid_method
    #def events_of_job(self, jobNum):
    #    return self.events.filter_by( eventClass=evCls ).count()
    #    #return len([ e for e in self.events
    #    #    if evCls == e.eventClass ])

    #@events_num_of_class.expression
    #def events_of_job(cls, jobNum):
    #    return (select([sqlalchemy.func.count(Event.child_id)]).
    #            where(Event.procID == cls.name).
    #            where(Event.taskID == cls.taskID).
    #            label("events_of_class")
    #            )


class Event(db.Model):
    """
    Reflects the process' event. May be one of the following types:
        - SUBMITTED: corresponds to process being sent to the computational
        back-end (HTCondor, LSF, etc). May not be created (?).
        - STARTED: process started computation
        - READY/PROGRESS/BEAT: process notifies us that it is still running
        - DONE/TERMINATED/FAILED: process done its job (successfully or not)
    Events may bear some arbitrary payload for custom usage.
    The submitted/started event carries only the timestamp.
    """
    __tablename__ = 'events'
    # Event ID
    id = db.Column(db.Integer, primary_key=True)
    # Event sent time (self-signed by event)
    sentAt = db.Column(db.DateTime)
    # Event recieved time
    recievedAt = db.Column(db.DateTime, default=datetime.datetime.utcnow)
    # Arbitrary event content
    payload = db.Column(db.String)
    # Incremental progress value brought by event
    progress = db.Column(db.Integer, default=0)
    # Event class string
    eventClass = db.Column(db.String)
    # Host self-identification (hostname, no reverse DNS lookup)
    hostname = db.Column(db.String)
    # Request-signed IP
    clientIP = db.Column(db.String)
    # If associated process is an array, this column denotes the particular
    # number of the physical process inside the array
    procNumInArray = db.Column(db.Integer)
    #
    process = db.relationship( 'Process'
                             , back_populates='events' )
    procID = db.Column(db.String)
    taskID = db.Column(db.String)
    __table_args__ = (sqlalchemy.schema.ForeignKeyConstraint([procID, taskID],
                                                             [Process.name, Process.taskID]),
                      {})

