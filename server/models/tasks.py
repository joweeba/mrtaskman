"""Representation of a Task and related classes."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

from google.appengine.ext import db

import datetime
import logging

from util import db_properties


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
  config = db_properties.JsonProperty(required=True)
  scheduled_by = db.UserProperty(required=False)
  scheduled_time = db.DateTimeProperty(required=False, auto_now_add=True)
  state = db.StringProperty(
      required=True,
      choices=(TaskStates.SCHEDULED,
               TaskStates.ASSIGNED,
               TaskStates.COMPLETE),
      default=TaskStates.SCHEDULED)
  attempts = db.IntegerProperty(required=True, default=0)
  max_attempts = db.IntegerProperty(required=True, default=3)
  executor_requirements = db.StringListProperty(required=True)

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


def MakeParentKey():
  return db.Key.from_path('TaskParent', '0')

def Schedule(name, config, scheduled_by, executor_requirements):
  """Adds a new Task with given name, config, user and requirements."""
  def tx():
    task = Task(parent=MakeParentKey(),
                name=name,
                config=config,
                scheduled_by=scheduled_by,
                executor_requirements=executor_requirements)
    db.put(task)
    return task
  return db.run_in_transaction(tx)


def GetById(task_id):
  """Retrieves Task with given integer task_id."""
  return Task.get_by_id(task_id)


def DeleteById(task_id):
  """Deletes Task with given integer task_id."""
  task = GetById(task_id)
  if task is None:
    return False
  task.delete()
  return True


def Assign(worker, executor_capabilities):
  """Looks for Tasks worker can execute, assigning one if possible.

  Args:
    worker: Name of worker as str.
    executor_capabilities: Capabilities as list of str.

  Returns: 
    Task if a Task was assigned, None otherwise.
  """
  assert worker
  assert executor_capabilities

  logging.info('Trying to assign task for %s', executor_capabilities)
  def tx():
    for executor_capability in executor_capabilities:
      task = (Task.all()
                  .ancestor(MakeParentKey())
                  .filter('state =', TaskStates.SCHEDULED)
                  .filter('executor_requirements =', executor_capability)
                  .get())
      if task is not None:
        task.state = TaskStates.ASSIGNED
        task.assigned_time = datetime.datetime.now()
        task.assigned_worker = worker
        logging.info('Assigning task %s to %s for %s.',
                     task.key().id_or_name(),
                     worker,
                     executor_capability)
        db.put(task)
        logging.info('Assignment successful.')
        return task
    return None
  return db.run_in_transaction(tx)
