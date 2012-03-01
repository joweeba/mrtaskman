# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""Representation of a Task and related classes."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

from google.appengine.api import urlfetch
from google.appengine.api import taskqueue
from google.appengine.ext import db
from google.appengine.ext.blobstore import blobstore

import datetime
import json
import logging
import urllib
import webapp2

from util import db_properties
from util import parsetime


class Error(Exception):
  pass


class TaskNotFoundError(Error):
  pass


class TaskTimedOutError(Error):
  pass


class TaskStates(object):
  SCHEDULED = 'scheduled'
  ASSIGNED = 'assigned'
  COMPLETE = 'complete'


class TaskOutcomes(object):
  SUCCESS = 'success'
  TIMED_OUT = 'timed_out'
  FAILED = 'failed'


class TaskResult(db.Model):
  """The results of a Task, including logs and execution time."""
  exit_code = db.IntegerProperty(required=True)
  execution_time = db.FloatProperty(required=False)
  stdout = blobstore.BlobReferenceProperty(required=False)
  stderr = blobstore.BlobReferenceProperty(required=False)
  stdout_download_url = db.TextProperty(required=False)
  stderr_download_url = db.TextProperty(required=True)
  # Should be populated if task execution involved a device.
  device_serial_number = db.StringProperty(required=False)
  result_metadata = db.TextProperty(required=False)


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
  priority = db.IntegerProperty(required=True, default=0)

  # Set once state == TaskStates.ASSIGNED.
  assigned_time = db.DateTimeProperty(required=False)
  assigned_worker = db.TextProperty(required=False)

  # Set once state == TaskStates.COMPLETE.
  completed_time = db.DateTimeProperty(required=False)
  outcome = db.StringProperty(
      required=False,
      choices=(TaskOutcomes.SUCCESS,
               TaskOutcomes.TIMED_OUT,
               TaskOutcomes.FAILED))
  result = db.ReferenceProperty(TaskResult)


def MakeParentKey():
  return db.Key.from_path('TaskParent', '0')


def Schedule(name, config, scheduled_by, executor_requirements, priority=0):
  """Adds a new Task with given name, config, user and requirements."""
  task = Task(parent=MakeParentKey(),
              name=name,
              config=config,
              scheduled_by=scheduled_by,
              executor_requirements=executor_requirements,
              priority=priority)
  db.put(task)
  return task


def GetById(task_id):
  """Retrieves Task with given integer task_id."""
  key = db.Key.from_path('TaskParent', '0', 'Task', task_id)
  return db.get(key)


def DeleteById(task_id):
  """Deletes Task with given integer task_id."""
  task = GetById(task_id)
  if task is None:
    return False
  task.delete()
  return True


def GetByExecutor(executor, limit=1000, keys_only=False):
  """Retrieves a list of tasks waiting for a given executor."""
  tasks = (Task.all(keys_only=keys_only)
               .ancestor(MakeParentKey())
               .filter('state =', TaskStates.SCHEDULED)
               .filter('executor_requirements =', executor)
               .fetch(limit=limit))
  return tasks


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
  def tx(executor_capability):
    task = (Task.all()
                .ancestor(MakeParentKey())
                .filter('state =', TaskStates.SCHEDULED)
                .filter('executor_requirements =', executor_capability)
                .order('-priority')
                .get())
    if task is not None:
      if task.state != TaskStates.SCHEDULED:
        return None
      task.state = TaskStates.ASSIGNED
      task.assigned_time = datetime.datetime.now()
      task.assigned_worker = worker
      task.attempts += 1
      logging.info('Assigning task %s to %s for %s.',
                   task.key().id_or_name(),
                   worker,
                   executor_capability)
      db.put(task)
      logging.info('Assignment successful.')
      ScheduleTaskTimeout(task)
      return task
    return None

  for executor_capability in executor_capabilities:
    task = db.run_in_transaction(tx, executor_capability)
    if task:
      return task
  return None


def UploadTaskResult(task_id, attempt, exit_code,
                     execution_time, stdout, stderr,
                     stdout_download_url, stderr_download_url,
                     device_serial_number, result_metadata):
  logging.info('Trying to upload result for task %d attempt %d',
               task_id, attempt)
  def tx():
    task = GetById(task_id)

    # Validate that task is in a state to accept results from worker.
    if not task:
      raise TaskNotFoundError()
    if task.attempts != attempt:
      logging.info('Attempts: %d, attempt: %d', task.attempts, attempt)
      raise TaskTimedOutError()
    # Here we allow a timed out task to publish results if it hasn't
    # been scheduled to another worker yet.
    if task.state not in [TaskStates.ASSIGNED, TaskStates.SCHEDULED]:
      logging.info('task.state: %s', task.state)
      raise TaskTimedOutError()

    # Mark task as complete and place results.
    task.completed_time = datetime.datetime.now()
    if exit_code == 0:
      task.outcome = TaskOutcomes.SUCCESS
    else:
      task.outcome = TaskOutcomes.FAILED
    task.state = TaskStates.COMPLETE

    task_result = TaskResult(parent=task,
                             exit_code=exit_code,
                             execution_time=execution_time,
                             stdout=stdout,
                             stderr=stderr,
                             stdout_download_url=stdout_download_url,
                             stderr_download_url=stderr_download_url,
                             device_serial_number=device_serial_number,
                             result_metadata=result_metadata)
    task_result = db.put(task_result)

    task.result = task_result
    db.put(task)
    return task
  task = db.run_in_transaction(tx)

  logging.info('Insert succeeded.')
  config = json.loads(task.config)
  try:
    webhook = config['task']['webhook']
    logging.info('invoking webhook: %s', webhook)
    payload = urllib.urlencode({'task_id': task_id}).encode('utf-8')
    fetched = urlfetch.fetch(url=webhook, method='POST', payload=payload,
        headers={'Content-Type':
            'application/x-www-form-urlencoded;encoding=utf-8'})
    logging.info('Webhook invoked with status %d: %s.', fetched.status_code,
        fetched.content)
  except Exception, e:
    logging.exception(e)
    logging.info('No webhook, or error invoking webhook.')


def GetTaskTimeout(task, default=datetime.timedelta(minutes=15)):
  """Returns task timeout as timedelta.

  Defaults to 15 minutes if no timeout is specified.

  A worker is given 3 minutes longer than the task timeout to allow for
  the overhead of downloading and installing packages.
  """
  config = task.config
  parsed_config = json.loads(config)
  timeout_str = parsed_config['task'].get('timeout', None)
  if not timeout_str:
    return default
  return parsetime.ParseTimeDelta(timeout_str) + datetime.timedelta(minutes=3)


def ScheduleTaskTimeout(task):
  """Schedules a timeout for the given assigned Task.

  Called by Assign to enforce Task timeouts.
  """
  timeout = GetTaskTimeout(task)
  timeout_task = taskqueue.Task(
      eta=(datetime.datetime.now() + timeout),
      method='POST',
      params={'task_key': task.key(),
              'task_attempt': task.attempts},
      url='/tasks/timeout')
  timeout_task.add(transactional=True)


class TaskTimeoutHandler(webapp2.RequestHandler):
  """Handles Task timeout firing.

  A Task may have completed successfully before the handler fires,
  in which case a timeout did not occur and this handler will not
  modify the completed Task.
  """
  def post(self):
    task_key = self.request.get('task_key')
    task_attempt = int(self.request.get('task_attempt'))
    assert task_key

    def tx():
      task = db.get(task_key)
      if not task:
        logging.info('Timed out Task %s was deleted.', task_key)
        return
      if (task.state == TaskStates.ASSIGNED and
          task.attempts == task_attempt):
        if task.attempts >= task.max_attempts:
          task.state = TaskStates.COMPLETE
          task.outcome = TaskOutcomes.TIMED_OUT
          db.put(task)
        else:
          # Remember to enforce uploading task outcome to check
          # both state and attempts.
          task.state = TaskStates.SCHEDULED
          # task.assigned_worker intentionally left so we can see
          # who timed out.
          db.put(task)
    db.run_in_transaction(tx)


def DeleteByExecutor(executor):
  delete_task = taskqueue.Task(
      method='POST',
      url='/executors/%s/deleteall' % executor)
  delete_task.add()


class DeleteAllByExecutorHandler(webapp2.RequestHandler):
  """Deletes all tasks for a given executor."""
  def post(self, executor):
    count = 0
    while True:
      task_keys = GetByExecutor(executor, limit=1000, keys_only=True)
      if not task_keys:
        logging.info('Done. Deleted %d tasks total.', count)
        return
      logging.info('Deleting %d tasks.', len(task_keys))
      count += len(task_keys)
      db.delete(task_keys)


app = webapp2.WSGIApplication([
    ('/tasks/timeout', TaskTimeoutHandler),
    ('/executors/([a-zA-Z0-9]+)/deleteall', DeleteAllByExecutorHandler),
    ], debug=True)
