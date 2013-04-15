# Copyright 2012 uTest, Inc. All Rights Reserved.

"""Handlers to expose pipeline."""

__author__ = 'Jeff Carollo (jeffc@utest.com)'


import logging
import webapp2

from index import migrate_tasks_pipeline
from index import task_results_pipeline


class IndexHandler(webapp2.RequestHandler):
  def get(self):
    self.response.out.write('''
<html>
<head><title>Index</title></head>
<body>
<form method="POST" action='/index'>
<input type="hidden" name="action" value="migrate_tasks"></input>
<input type="submit" value="Migrate Tasks"></input>
</form>
<form method="POST" action='/index'>
<input type="hidden" name="action" value="task_results"></input>
<input type="submit" value="Task Results"></input>
</form>
</body>
</html>
    ''')
    self.response.headers['Content-Type'] = 'text/html'

  def post(self):
    logging.info('request: %s', self.request.body.decode('utf-8'))
    action = self.request.get('action', None)
    if not action:
      self.response.out.write('Need to give an action.')
      self.response.set_status(400)
      return

    if action == 'migrate_tasks':
      pipeline = migrate_tasks_pipeline.MigrateTasksPipeline()
      pipeline.start()
      self.redirect(
          pipeline.base_path + "/status?root=" + pipeline.pipeline_id)
      return
    if action == 'task_results':
      pipeline = task_results_pipeline.TaskResultsPipeline()
      pipeline.start()
      self.redirect(
          pipeline.base_path + "/status?root=" + pipeline.pipeline_id)
      return

    self.response.out.write('Invalid action: %s' % action)
    self.response.set_status(400)


app = webapp2.WSGIApplication([
    ('/index', IndexHandler),
    ], debug=True)
