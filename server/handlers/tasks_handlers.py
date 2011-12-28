#!usr/bin/python

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
    content_type = self.request.headers['Content-Type']
    if 'application/json' not in content_type:
      logging.info('Content-Type: %s', content_type)
      self.response.out.write('Content-Type must be application/json.\n')
      self.response.set_status(415)
      return

    body = self.request.body.decode('utf-8')
    if body is None:
      self.response.out.write('config is required in message body\n')
      self.response.set_status(400)
      return

    config = urllib.unquote(body)
    logging.info('Config: %s', config)

    try:
      parsed_config = json.loads(config)
      if parsed_config is None:
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

    user = users.GetCurrentUser()

    scheduled_task = tasks.Schedule(name, config, scheduled_by=user)
    
    try:
      email = user.email()
    except:
      email = 'unauthenticated'

    task_id = scheduled_task.key().id_or_name()
    logging.info('%s created task %s with ID %s.',
        email, name, task_id)
    logging.info('Config: %s', config)

    self.response.headers['Content-Type'] = 'application/json'
    self.response.out.write('{id: \'%s\'}' % task_id)


class TasksHandler(webapp2.RequestHandler):
  def get(self, task_id):
    """Retrieves a single task given by task_id."""
    task_id = int(task_id)
    task = tasks.GetById(task_id)

    if task is None:
      self.error(404)
      return

    logging.info(task)
    logging.info(task.name)

    self.response.headers['Content-Type'] = 'application/json'
    json.dump(model_to_dict.ModelToDict(task), self.response.out, indent=2)
    self.response.out.write('\n')

  def delete(self, task_id):
    """Removes a single task given by task_id."""
    task_id = int(task_id)
    success = tasks.DeleteById(task_id)
    if not success:
      self.error(404)
      return
    # 200 OK.


# Ignore for this code review.
class TasksAssignHandler(webapp2.RequestHandler):
  """Handles /tasks/assign, which hands off tasks to workers."""

  def put(self):
    pass


app = webapp2.WSGIApplication([
    ('/tasks/([0-9]+)', TasksHandler),
    ('/tasks/assign', TasksAssignHandler),
    ('/tasks/schedule', TasksScheduleHandler),
    ], debug=True)
