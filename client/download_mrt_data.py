#!/usr/bin/python
# Copyright 2012 uTest, Inc. All Rights Reserved.

"""Utility for consuming REST API for MrTaskman data."""

__author__ = 'Jeff Carollo (jeffc@utest.com)'

import codecs
import csv
import datetime
import json
import logging
import time
import urllib
import urllib2
import sys


class Error(Exception):
  pass
class DownloadError(Error):
  pass


BASE_URL = 'http://4.mrtaskman.appspot.com'


# Portable MakeHttpRequest adapter.
try:
  from google.appengine.api import urlfetch
  from google.appengine.runtime import apiproxy_errors

  def MakeHttpRequest(url, method='GET', headers={}, body=None, timeout=25):
    """Makes HTTP request and returns read response.

    Raises urllib2.HTTPError on non-200 response.
    """
    try:
      response = urlfetch.fetch(
          url, payload=body, method=method, headers=headers, deadline=timeout)
    except (urlfetch.DeadlineExceededError, urlfetch.DownloadError,
            apiproxy_errors.DeadlineExceededError), e:
      logging.warning('Got urlfetch error:\n%s', e)
      raise DownloadError()
    response_body = response.content
    status_code = response.status_code
    headers = response.headers
    if 200 != status_code:
      if 404 == status_code:
        raise CrawlDoneError()
      class Readable:
        def __init__(self, data):
          self.data = data
          self.done_ = False

        def read(self):
          self.done_ = True
          return self.data

        def readline(self):
          if self.done_:
            return None
          self.done_ = True
          return self.data

      logging.warning('Got non-200 HTTP code: %s', status_code)
      raise DownloadError()
    else:
      return response_body
except ImportError:
  def MakeHttpRequest(url, method='GET', headers={}, body=None, timeout=15*60):
    """Makes HTTP request and returns read response.

    Raises urllib2.HTTPError on non-200 response.
    """
    request = urllib2.Request(url, body, headers)
    request.get_method = lambda: method

    response = urllib2.urlopen(request, timeout=timeout)
    response_body = response.read()
    return response_body


class UTF8Recoder:
  """
  Iterator that reads an encoded stream and reencodes the input to UTF-8
  """
  def __init__(self, f, encoding):
      self.reader = codecs.getreader(encoding)(f)

  def __iter__(self):
      return self

  def next(self):
      return self.reader.next().encode("utf-8")


class UnicodeReader:
  """
  A CSV reader which will iterate over lines in the CSV file "f",
  which is encoded in the given encoding.
  """

  def __init__(self, f, dialect=csv.excel, encoding="utf-8", **kwds):
      f = UTF8Recoder(f, encoding)
      self.reader = csv.reader(f, dialect=dialect, **kwds)

  def next(self):
      row = self.reader.next()
      return [unicode(s, "utf-8") for s in row]

  def __iter__(self):
      return self


def MakeTaskResultsAfterDateDownloadUrl(after_date, limit=1000, cursor=None):
  url = '%s/api/task_results/list_after_date/after_date/%s' % (
      BASE_URL, after_date)
  url += '?limit=%d' % int(limit)
  if cursor is not None:
    url += '&cursor=%s' % cursor
  return url


def DownloadTaskResultsAfterDate(after_date, limit=1000, cursor=None):
  """Downloads TaskResult data with given parameters.

  Returns a csv_data#task_results instance.
  """
  url = MakeTaskResultsAfterDateDownloadUrl(after_date, limit, cursor)
  logging.info('Fetching from url: %s', url)

  response_json = MakeHttpRequest(url).decode('utf-8', 'ignore')
  device_data = json.loads(response_json)
  return device_data


def WriteTaskResultsAfterDate(after_date, limit=1000):
  data = DownloadTaskResultsAfterDate(after_date, limit)
  headers = data['headers']
  sys.stdout.write(','.join(headers))
  sys.stdout.write('\n')
  sys.stdout.write(data['data'].encode('utf-8', 'ignore'))
  next_cursor = data['next_cursor']
  last_cursor = None
  count = 1

  while next_cursor != last_cursor:
    logging.info('wrote some records. next_cursor: %s', next_cursor)
    try:
      data = DownloadTaskResultsAfterDate(after_date, limit, next_cursor)
      sys.stdout.write(data['data'].encode('utf-8', 'ignore'))
    except Exception, e:
      logging.exception(e)
      logging.info('Retrying.')
      continue
    last_cursor = next_cursor
    next_cursor = data['next_cursor']
    count += 1
  logging.info('All records written.')
  return 0


class DeviceStat(object):
  def __init__(self, device_name):
    self.device_name = device_name
    self.total_runs = 0
    self.successes = 0
    self.failures = 0

  def AddData(self, row):
    task_id = row[0]
    executor = row[1]
    assigned_worker = row[2]
    assigned_time = row[3]
    completed_time = row[4]
    exit_code = int(row[5])
    stderr_url = row[6]
    stdout_url = row[7]
    stderr_blobkey = row[8]
    stdout_blobkey = row[9]

    if exit_code == 0:
      self.total_runs += 1
      self.successes += 1
    elif exit_code == 212:
      self.total_runs += 1
      self.failures += 1


def ProcessAggregateStatsFromTaskResultsCsvFile(csv_filename):
  csv_file = open(csv_filename, 'r')
  fieldnames = csv_file.readline().split(',')
  reader = UnicodeReader(csv_file)

  device_stats = {}
  for csv_row in reader:
    executor = csv_row[1]
    device_stat = device_stats.get(executor, DeviceStat(executor))
    device_stats[executor] = device_stat
    device_stat.AddData(csv_row)

  print 'device,total_runs,successes,failures,success_pct,failure_pct'
  for (device, device_stat) in device_stats.iteritems():
    print '%s,%s,%s,%s,%s,%s' % (
        device,
        device_stat.total_runs,
        device_stat.successes,
        device_stat.failures,
        float(device_stat.successes) / float(device_stat.total_runs) * 100,
        float(device_stat.failures) / float(device_stat.total_runs) * 100)

  return 0


def Usage():
  sys.stderr.write(
'''python download_mrt_data.py [command] [args]
Writes data in CSV format to STDOUT.

Valid commands are:
 task_results [after_date]
 process_task_results [csv_filename]
 timestamp [year] [month] [day] [hour] [minute] [second]
 help (prints this message)
''')


def main(argv):
  _ = argv.pop(0)  # Shift off program name.

  FORMAT = '%(asctime)-15s %(message)s'
  logging.basicConfig(format=FORMAT, level=logging.INFO)

  command = argv.pop(0)
  if command == 'task_results':
    after_date = argv.pop(0)
    after_date = urllib.quote(after_date)
    return WriteTaskResultsAfterDate(after_date, limit=1000)
  if command == 'process_task_results':
    filename = argv.pop(0)
    return ProcessAggregateStatsFromTaskResultsCsvFile(filename)
  if command == 'timestamp':
    year = int(argv.pop(0))
    month = int(argv.pop(0))
    day = int(argv.pop(0))
    hour = int(argv.pop(0))
    minute = int(argv.pop(0))
    second = int(argv.pop(0))
    date = datetime.datetime(year, month, day, hour, minute, second)
    print time.mktime(date.timetuple())
  elif command == 'help':
    Usage()
    return 0
  else:
    sys.stderr.write('Invalid command: %s\n' % command)
    Usage()
    return -1
  return 0


if __name__ == '__main__':
  main(sys.argv)
