# Copyright 2012 uTest, Inc. All Rights Reserved.

"""API for fetching data remotely."""

from google.appengine.ext import blobstore
from google.appengine.ext import db
from google.appengine.ext.db import datastore_query
from google.appengine.ext.webapp import blobstore_handlers

from models import tasks
from util import device_info

import csv
import datetime
import json
import StringIO
import urllib
import webapp2


def FormatModelDataAsCsv(models, keys):
  """Takes list of db.Models and returns CSV representation as StingIO."""
  data_csv = StringIO.StringIO()
  data_writer = csv.DictWriter(data_csv, keys)
  for model in models:
    d = db.to_dict(model)
    encoded_d = {}
    for (key, value) in d.iteritems():
      if isinstance(value, basestring):
        encoded_d[key] = value.encode('utf-8', 'ignore')
      else:
        encoded_d[key] = value
    data_writer.writerow(encoded_d)
  data_csv.flush()
  return data_csv


def Utf8Encode(string):
  return string.encode('utf-8', 'ignore')


def GetExecutor(executor):
  device_data = device_info.GetDeviceInfo(executor)
  if device_data is not None:
    executor = device_data['device_name']
  return executor


TASK_RESULT_KEYS = [
    'task_id',
    'executor',
    'assigned_worker',
    'assigned_time',
    'completed_time',
    'exit_code',
    'stderr_url',
    'stdout_url',
    'stderr_blobkey',
    'stdout_blobkey',
]
def FormatTaskResultsAsCsv(task_list):
  """Specially format Tasks with TaskResults for CSV transmission."""
  data_csv = StringIO.StringIO()
  data_writer = csv.DictWriter(data_csv, TASK_RESULT_KEYS)

  for task in task_list:
    if task.executor_requirements[0] == 'macos':
      continue
    executor = GetExecutor(task.executor_requirements[0])
    encoded_d = {}
    encoded_d['task_id'] = task.key().id()
    encoded_d['executor'] = Utf8Encode(executor)
    encoded_d['assigned_worker'] = Utf8Encode(task.assigned_worker)
    encoded_d['assigned_time'] = task.assigned_time
    encoded_d['completed_time'] = task.completed_time
    encoded_d['exit_code'] = task.result.exit_code
    encoded_d['stderr_url'] = Utf8Encode(task.result.stderr_download_url)
    encoded_d['stdout_url'] = Utf8Encode(task.result.stdout_download_url)
    encoded_d['stderr_blobkey'] = Utf8Encode(task.result.stderr.key().__str__())
    encoded_d['stdout_blobkey'] = Utf8Encode(task.result.stdout.key().__str__())
    data_writer.writerow(encoded_d)
  data_csv.flush()
  return data_csv


class ListResultsAfterDate(webapp2.RequestHandler):
  """Retrieves a special-formatted list of results newer than after_date."""
  def get(self, after_date):
    cursor = self.request.get('cursor', None)
    limit = int(self.request.get('limit', 1000))

    try:
      after_date = int(urllib.unquote(after_date))
    except:
      self.response.out.write('after_date must be an integer timestamp.')
      self.response.set_status(400)
      return

    after_date = datetime.datetime.fromtimestamp(after_date)

    # Fetch data.
    (results, next_cursor) = tasks.GetResultsAfterDate(
        after_date, limit, cursor)

    # Format data as CSV.
    data_csv = FormatTaskResultsAsCsv(results)

    # Create response.
    response = {}
    response['kind'] = 'csv_data#task_results'
    response['headers'] = TASK_RESULT_KEYS
    response['data'] = data_csv.getvalue()
    response['next_cursor'] = next_cursor

    # Write response.
    json.dump(response, self.response.out, check_circular=False)
    self.response.headers['Content-Type'] = 'application/json'


app = webapp2.WSGIApplication([
  ('/api/task_results/list_after_date/after_date/(.+)', ListResultsAfterDate),
  ], debug=True)
