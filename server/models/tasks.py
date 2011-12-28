"""Representation of a Task and related classes."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

from google.appengine.ext import db


class TaskStates(object):
  SCHEDULED = 'scheduled'
  ASSIGNED = 'assigned'
  COMPLETE = 'complete'
  

class TaskOutcomes(object):
  SUCCESS = 'success'
  FAILED = 'failed'


class TaskResult(db.Model):
  """The results of a Task, including logs and execution time."""
  exit_code = db.IntegerProperty(required=True)
  execution_time = db.FloatProperty(required=False)
  stdout = db.TextProperty(required=False)
  stderr = db.TextProperty(required=False)


class Task(db.Model):
  """MrTaskman's representation of a Task.

  Includes metadata not needed in a Task config.
  """
  # Set when a task is created.
  name = db.StringProperty(required=True)
  config = db.TextProperty(required=True)
  scheduled_by = db.UserProperty(required=False)
  scheduled_time = db.DateTimeProperty(required=False, auto_now_add=True)
  state = db.StringProperty(
      required=True,
      choices=(TaskStates.SCHEDULED,
               TaskStates.ASSIGNED,
               TaskStates.COMPLETE),
      default=TaskStates.SCHEDULED)
  attempts = db.IntegerProperty(required=True, default=1)
  max_attempts = db.IntegerProperty(required=True, default=3)

  # Set once state == TaskStates.ASSIGNED.
  assigned_time = db.DateTimeProperty(required=False)
  assigned_worker = db.TextProperty(required=False)

  # Set once state == TaskStates.COMPLETE.
  completed_time = db.DateTimeProperty(required=False)
  outcome = db.StringProperty(
      required=False,
      choices=(TaskOutcomes.SUCCESS,
               TaskOutcomes.FAILED))
  result = db.ReferenceProperty(TaskResult)


def Schedule(name, config, scheduled_by):
  """Adds a new task with given name, config and user."""
  def tx():
    task = Task(name=name,
                config=config,
                scheduled_by=scheduled_by)
    db.put(task)
    return task
  return db.run_in_transaction(tx)


def GetById(task_id):
  """Retrieves task with given integer task_id."""
  return Task.get_by_id(task_id)


def DeleteById(task_id):
  task = GetById(task_id)
  if task is None:
    return False
  task.delete()
  return True
