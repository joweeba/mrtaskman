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
import urllib2

import gflags
import package_installer
from client import mrtaskman_api
from common import http_file_upload


FLAGS = gflags.FLAGS


class MacOsWorker(object):
  """Executes macos tasks."""

  def __init__(self):
    self.api_ = mrtaskman_api.MrTaskmanApi()
    self.worker_name_ = 'MacOsWorker1of1'
    self.hostname_ = 'leonardo'
    self.capabilities_ = {'executor': ['macos']}
    self.executors_ = {'macos': self.ExecuteTask}

  def AssignTask(self):
    """Makes a request to /tasks/assign to get assigned a task.

    Returns:
      Task if a task was assigned, or None.
    """
    try:
      task = self.api_.AssignTask(self.worker_name_, self.hostname_,
                                  self.capabilities_)
      return task
    except urllib2.HTTPError, e:
      logging.info('Got %d HTTP response from MrTaskman on AssignTask.',
                   e.code)
      return None

  def SendResponse(self, response_url, stdout, stderr, task_result):
    try:
      self.api_.SendTaskResult(response_url, stdout, stderr, task_result)
      task_id = task_result['task_id']
      logging.info('Successfully sent response for task %s: %s',
                   task_id, self.api_.MakeTaskUrl(task_id))
    except urllib2.HTTPError, error_response:
      body = error_response.read()
      code = error_response.code
      logging.warning('SendResponse HTTPError code %d\n%s',
                      code, body)

  def PollAndExecute(self):
    while True:
      logging.info('Attempting to get a task.')
      task = self.AssignTask()
      
      if not task:
        logging.info('No task. Sleeping.')
        time.sleep(10)
        continue

      logging.info('Got a task:\n%s\n', json.dumps(task, 'utf-8', indent=2))

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
      # This will invoke ExecuteTask below.
      (results, stdout, stderr) = executor(task_id, attempt, task, config)

      self.SendResponse(task_complete_url,
                        stdout.read(),
                        stderr.read(),
                        results)
      # Loop back up and poll for the next task.
 
  def ExecuteTask(self, task_id, attempt, task, config):
    logging.info('Executing task %s', task_id)

    try:
      tmpdir = package_installer.TmpDir()

      # Download the files we need from the server.
      files = config['files']
      self.DownloadAndStageFiles(files)

      # Install any packages we might need.
      packages = []
      try:
        packages = config['task']['packages']
      except KeyError:
        logging.info('No packages.')
        pass
      self.DownloadAndInstallPackages(packages, tmpdir)

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
        'attempt': attempt,
        'exit_code': exit_code,
        'execution_time': 5.0
      }
      return (results, stdout, stderr)
    finally:
      #tmpdir.CleanUp()
      pass

  def RunCommandRedirectingStdoutAndStderrWithTimeout(
      self, command, timeout):
    process = subprocess.Popen(args=command,
                               shell=True,
                               stdout=subprocess.PIPE,
                               stderr=subprocess.PIPE)
    # TODO: Implement timeout.
    while None == process.poll():
      time.sleep(0.02)
    return (process.returncode, process.stdout, process.stderr)

  def DownloadAndStageFiles(self, files):
    logging.info('Staging files: %s', files)
    # TODO: Stage files.

  def DownloadAndInstallPackages(self, packages, tmpdir):
    for package in packages:
      package_installer.DownloadAndInstallPackage(
          package['name'], package['version'],
          tmpdir.GetTmpDir())


def main(argv):
  try:
    argv = FLAGS(argv)
  except gflags.FlagsError, e:
    sys.stderr.write(Usage())
    sys.stderr.write('%s\n' % e)
    sys.exit(1)

  try:
    logging.basicConfig(level=logging.DEBUG)

    macos_worker = MacOsWorker()
    # Run forever, executing tasks from the server when available.
    macos_worker.PollAndExecute()
  finally:
    logging.shutdown()


if __name__ == '__main__':
  main(sys.argv)
