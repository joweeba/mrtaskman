"""Handlers for the MrTaskman Tasks API."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

from google.appengine.api import users

import json
import logging
import urllib
import webapp2

from models import tasks
from util import model_to_dict


class TasksScheduleHandler(webapp2.RequestHandler):
  """Handles the creation of a new Task, also known as scheduling."""

  def post(self):
    """TODO(jeff.carollo): Specify request and response format."""
    content_type = self.request.headers['Content-Type']
    if 'application/json' not in content_type:
      logging.info('Content-Type: %s', content_type)
      self.response.out.write('Content-Type must be application/json.\n')
      self.response.set_status(415)
      return

    body = self.request.body.decode('utf-8')
    if body is None:
      self.response.out.write('Config is required in message body\n')
      self.response.set_status(400)
      return

    config = urllib.unquote(body)
    logging.info('Config: %s', config)

    try:
      parsed_config = json.loads(config, 'utf-8')
      if not parsed_config:
        raise Exception('json could not parse config.')
    except Exception, e:
      self.response.out.write('Failure parsing config.\n')
      self.response.out.write(e)
      self.response.out.write('\n')
      self.response.set_status(400)
      return

    try:
      name = parsed_config['task']['name']
    except KeyError, e:
      self.response.out.write('Failure parsing config.\n')
      self.response.out.write('task.name is required\n')
      self.response.set_status(400)
      return

    try:
      executor_requirements = parsed_config['task']['requirements']['executor']
      assert executor_requirements
      assert isinstance(executor_requirements, list)
    except KeyError, e:
      self.response.out.write('Failure parsing config.\n')
      self.response.out.write('task.requirements.executor is required\n')
      self.response.set_status(400)
      return
    except AssertionError, e:
      self.response.out.write('Failure parsing config.\n')
      self.response.out.write(
          'task.requirements.executor must be a non-empty list of strings.\n')
      self.response.set_status(400)
      return

    user = users.GetCurrentUser()

    scheduled_task = tasks.Schedule(
        name, config, user, executor_requirements)
    
    try:
      email = user.email()
    except:
      email = 'unauthenticated'

    task_id = scheduled_task.key().id_or_name()
    logging.info('%s created task %s with ID %s.',
        email, name, task_id)
    logging.info('Config: %s', config)

    # Success. Write response.
    self.response.headers['Content-Type'] = 'application/json'
    response = dict()
    response['id'] = task_id
    response['kind'] = 'mrtaskman#taskid'
    json.dump(response, self.response.out, indent=2)
    self.response.out.write('\n')


class TasksHandler(webapp2.RequestHandler):
  def get(self, task_id):
    """Retrieves a single task given by task_id."""
    # TODO(jeff.carollo): Specify request and response format."""
    task_id = int(task_id)
    task = tasks.GetById(task_id)

    if task is None:
      self.error(404)
      return

    # Success. Write response. 
    self.response.headers['Content-Type'] = 'application/json'
    response = model_to_dict.ModelToDict(task)
    response['kind'] = 'mrtaskman#task'
    json.dump(response, self.response.out, indent=2)
    self.response.out.write('\n')

  def delete(self, task_id):
    """Removes a single task given by task_id."""
    task_id = int(task_id)
    success = tasks.DeleteById(task_id)
    if not success:
      self.error(404)
      return
    # 200 OK.


class TasksAssignHandler(webapp2.RequestHandler):
  """Handles /tasks/assign, which hands off tasks to workers."""

  def put(self):
    # TODO(jeff.carollo): Specify request and response format."""
    body = self.request.body.decode('utf-8')
    if body is None:
      self.response.out.write('AssignRequest is required in message body\n')
      self.response.set_status(400)
      return

    assign_request = urllib.unquote(body)
    logging.info('assign_request: %s', assign_request)

    try:
      parsed_request = json.loads(assign_request)
      if not parsed_request:
        raise Exception('json could not parse AssignRequest.')
    except Exception, e:
      self.response.out.write('Failure parsing AssignRequest.\n')
      self.response.out.write(e)
      self.response.out.write('\n')
      self.response.set_status(400)
      return

    # TODO(jeff.carollo): Make these real objects with validate methods.
    try:
      worker = parsed_request['worker']
    except KeyError, e:
      self.response.out.write('AssignRequest.worker is required.\n')
      self.response.out.write(e)
      self.response.out.write('\n')
      self.response.set_status(400)
      return

    try:
      executor_capabilities = parsed_request['capabilities']['executor']
    except KeyError, e:
      self.response.out.write(
          'AssignRequest.capabilities.executor is required.\n')
      self.response.out.write(e)
      self.response.out.write('\n')
      self.response.set_status(400)
      return

    self.response.headers['Content-Type'] = 'application/json'
    response = dict()
    response['kind'] = 'TaskAssignment'
    response['tasks'] = []

    task = tasks.Assign(worker, executor_capabilities)

    if task is not None:
      task_dict = model_to_dict.ModelToDict(task)
      task_dict['kind'] = 'mrtaskman#task'
      response['tasks'] = [task_dict]

    json.dump(response, self.response.out, indent=2)
    self.response.out.write('\n')


app = webapp2.WSGIApplication([
    ('/tasks/([0-9]+)', TasksHandler),
    ('/tasks/assign', TasksAssignHandler),
    ('/tasks/schedule', TasksScheduleHandler),
    ], debug=True)
