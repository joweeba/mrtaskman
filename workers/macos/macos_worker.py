#!/usr/bin/python
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

"""MrTaskman worker script which executes MacOS commands."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

import httplib
import json
import logging
import StringIO
import subprocess
import sys
import time
import urlparse


class MacOsWorker(object):
  """Executes macos tasks."""

  def __init__(self,
               mrtaskman_host='mrtaskman.appspot.com',
               mrtaskman_port=None):
    self.worker_name_ = 'MacOsWorker1of1'
    self.hostname_ = 'leonardo'
    self.executors_ = {'macos': self.ExecuteMacosTask}
    self.connection_ = httplib.HTTPConnection(mrtaskman_host, mrtaskman_port,
                                              timeout=None)
    self.connection_.connect()

  def AssignTask(self):
    """Makes a request to /tasks/assign to get assigned a task.

    Returns:
      Parsed Task JSON if a task was assigned, or None.
    """
    # Construct /tasks/assign request to MrTaskman.
    assign_body = (
        """
        {
          "kind": "mrtaskman#assign_request",
          "worker": "%s",
          "hostname": "%s",
          "capabilities": {
            "executor": ["macos"]
          }
        }
        """ % (self.worker_name_, self.hostname_))
    self.connection_.request(
        method='PUT',
        url='/tasks/assign',
        body=assign_body,
        headers={'Accept': 'application/json'})

    response = self.connection_.getresponse()
    response_json = response.read()
    status = response.status
    logging.info('response status: %d', status)
    logging.info('response body: %s', response_json)
    if status == 200 and response_json:
      response_json = response_json.decode('utf-8')
      task = json.loads(response_json, 'utf-8')
      return task 
    return None

  def ExtractUrlPath(self, url):
    split = urlparse.urlsplit(url)
    return split.path

  def SendResponse(self, response_url, stdout, stderr, task_result):
    response_url = self.ExtractUrlPath(response_url)    
    print 'url_path: %s\n' % response_url
    task_result_json = json.dumps(task_result, 'utf-8', indent=2)
    BOUNDARY = u'------FORM_BOUNDARY--------'
    headers = {}
    headers['Content-Type'] = 'multipart/form-data; boundary=%s' % BOUNDARY
    BOUNDARY = u'--%s' % BOUNDARY
    body = u'\r\n'.join([
        BOUNDARY,
        u'Content-Disposition: form-data; name="task_result"',
        '',
        task_result_json,
        BOUNDARY,
        u'Content-Disposition: form-data; name="STDOUT"; filename="stdout"',
        u'Content-Type: application/octet-stream',
        u'',
        stdout,
        BOUNDARY,
        u'Content-Disposition: form-data; name="STDERR"; filename="stderr"',
        u'Content-Type: application/octet-stream',
        u'',
        stderr,
        BOUNDARY])

    logging.info('Body:\n%s', body)

    self.connection_.request(
        method='POST',
        url=response_url,
        body=body,
        headers=headers)

    response = self.connection_.getresponse()
    response_json = response.read()
    status = response.status
    logging.info('response status: %d', status)
    logging.info('response body: %s', response_json)
    if status == 200 and response_json:
      response_json = response_json.decode('utf-8')
      parsed_response = json.loads(response_json, 'utf-8')
      return parsed_response
    return None

  def PollAndExecute(self):
    while True:
      logging.info('Attempting to get a task.')
      task = self.AssignTask()     
      
      if not task:
        logging.info('No task. Sleeping.')
        time.sleep(10)
        continue

      logging.info('Got a task: %s', task)

      config = task['config']
      task_id = task['id']
      attempt = task['attempts']
      task_complete_url = task['task_complete_url']
      
      # Figure out which of our executors we can use.
      executor = None
      allowed_executors = config['task']['requirements']['executor']
      for allowed_executor in allowed_executors:
        executor = self.executors_[allowed_executor]
        if executor is not None:
          break
      
      if executor is None:
        logging.info('No matching executor from %s', allowed_executors)
        # Send error response to server so that it knows we can't do this one.
        continue

      # We've got a valid executor, so use it.
      # This will invoke ExecuteMacosTask below.
      (results, stdout, stderr) = executor(task_id, attempt, task, config)

      self.SendResponse(task_complete_url,
                        stdout.read(),
                        stderr.read(),
                        results)
      # Loop back up and poll for the next task.
 
  def ExecuteMacosTask(self, task_id, attempt, task, config):
    logging.info('Executing macos task %s', task_id)

    # Download the files we need from the server.
    files = config['files']
    self.DownloadAndStageFiles(files)

    # We probably don't want to run forever.
    timeout = config['task']['timeout']

    # Get our command and execute it.
    command = config['task']['command']

    (exit_code, stdout, stderr) = (
        self.RunCommandRedirectingStdoutAndStderrWithTimeout(
            command, timeout))

    logging.info('Executed %s with result %s', command, exit_code)

    results = {
      'kind': 'mrtaskman#task_complete_request',
      'task_id': task_id,
      'attempt': 1,
      'exit_code': exit_code,
      'execution_time': 5.0
    }
    return (results, stdout, stderr)

  def RunCommandRedirectingStdoutAndStderrWithTimeout(
      self, command, timeout):
    # TODO: Run command.
    stdout = file('/tmp/stdout', 'r', 0)
    stderr = file('/tmp/stderr', 'r', 0)
    process = subprocess.Popen(args=command,
                               shell=True,
                               stdout=stdout,
                               stderr=stderr)
    # TODO: Implement timeout.
    while None == process.poll():
      time.sleep(0.02)
    return (process.returncode, stdout, stderr)

  def DownloadAndStageFiles(self, files):
    logging.info('Staging files: %s', files)
    # TODO: Stage files.


def main(args):
  logging.basicConfig(level=logging.DEBUG)
  macos_worker = MacOsWorker('localhost', 8080)
  # Run forever, executing tasks from the server when available.
  macos_worker.PollAndExecute()


if __name__ == '__main__':
  main(sys.argv)
