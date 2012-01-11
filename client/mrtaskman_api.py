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

"""MrTaskman API client, which wraps MrTaskman REST API."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

import gflags
import json
import logging
import urllib2

from common import http_file_upload


FLAGS = gflags.FLAGS
gflags.DEFINE_string('mrtaskman_server', 'http://mrtaskman.appspot.com',
                     'URL of MrTaskman server to connect to.')


class MrTaskmanApi(object):
  """Client wrapper for MrTaskman REST API."""

  def __init__(self, mrtaskman_server=FLAGS.mrtaskman_server):
    self.mrtaskman_url = mrtaskman_server


  def GetTask(self, task_id):
    """Performs a tasks.get on given task_id.

    Args:
      task_id: Id of task to retrieve as int

    Returns:
      Task object.

    Raises:
      urllib2.HTTPError on non-200 response.
    """
    assert isinstance(task_id, int)

    path = '/tasks/%d' % task_id
    url = FLAGS.mrtaskman_server + path
    body = None
    headers = {'Accept': 'application/json'}
    request = urllib2.Request(url, body, headers)

    response = urllib2.urlopen(request)
    response_body = response.read()
    response_body = response_body.decode('utf-8')
    return json.loads(response_body, 'utf-8')

  def ScheduleTask(self, config):
    """Performs a tasks.schedule on given config object.

    Args:
      config: Config object to schedule

    Returns:
      ScheduleTaskResult object.

    Raises:
      urllib2.HTTPError on non-200 response.
    """
    assert config
    # TODO(jeff.carollo): Validate config.

    path = '/tasks/schedule'
    url = FLAGS.mrtaskman_server + path
    body = json.dumps(config, indent=2).encode('utf-8')
    headers = {'Accept': 'application/json',
               'Content-Type': 'application/json'}
    request = urllib2.Request(url, body, headers)
    request.get_method = lambda: 'POST'

    response = urllib2.urlopen(request)
    response_body = response.read()
    response_body = response_body.decode('utf-8')
    return json.loads(response_body, 'utf-8')

  def DeleteTask(self, task_id):
    """Performs a tasks.delete on given task_id.

    Args:
      task_id: Id of task to delete as int

    Returns:
      None

    Raises:
      urllib2.HTTPError on non-200 response.
    """
    assert isinstance(task_id, int)

    path = '/tasks/%d' % task_id
    url = FLAGS.mrtaskman_server + path
    body = None
    headers = {'Accept': 'application/json'}
    request = urllib2.Request(url, body, headers)
    request.get_method = lambda: 'DELETE'

    response = urllib2.urlopen(request)
    response.read()
    return

  def CreatePackage(self, create_package_request):
    """Performs a packages.create with given create_package_request.

    Args:
      create_package_request: mrtaskman#create_package_request object.

    Returns:
      mrtaskman#create_package_result object.

    Raises:
      urllib2.HTTPError on non-200 response.
    """
    assert create_package_request
    # TODO(jeff.carollo): Validate request.

    path = '/packages/create'

    # Get url to upload to.
    url = FLAGS.mrtaskman_server + path
    body = None
    headers = {'Accept': 'application/json'}
    request = urllib2.Request(url, body, headers)
    response = urllib2.urlopen(request)
    get_upload_url_response = response.read().decode('utf-8')
    get_upload_url_object = json.loads(get_upload_url_response, 'utf-8')
    upload_url = get_upload_url_object['upload_url']

    # Parse files from request.
    package_files = create_package_request['files']
    file_form_entries = []
    for package_file in package_files:
      file_form_entry = {}
      file_form_entry['name'] = package_file['form_name']
      file_form_entry['filename'] = package_file['filename']
      file_form_entry['filepath'] = package_file['client_path']
      file_form_entries.append(file_form_entry)

    # Upload to that URL.
    response = http_file_upload.SendMultipartHttpFormData(
        upload_url, 'POST', {},
        [{'name': 'manifest',
          'Content-Type': 'application.json; charset=utf-8',
          'data': json.dumps(create_package_request, 'utf-8', indent=2)}],
        file_form_entries)

    response_body = response.read()
    response_body = response_body.decode('utf-8')
    return json.loads(response_body, 'utf-8')

  def GetPackage(self, package_name, package_version):
    """Performs a package.get on given package_name and package_version.

    Args:
      package_name: Name of package to retrieve as str
      package_version: version of package to retrieve as int

    Returns:
      mrtaskman#package object

    Raises:
      urllib2.HTTPError on non-200 response.
    """
    assert package_name
    assert isinstance(package_version, int)

    path = '/packages/%s.%d' % (package_name, package_version)
    url = FLAGS.mrtaskman_server + path
    body = None
    headers = {'Accept': 'application/json'}
    request = urllib2.Request(url, body, headers)

    response = urllib2.urlopen(request)
    response_body = response.read()
    response_body = response_body.decode('utf-8')
    return json.loads(response_body, 'utf-8')

  def DeletePackage(self, package_name, package_version):
    """Performs a packages.delete on given package_name and package_version.

    Args:
      package_name: Name of package to delete as str
      package_version: version of package to delete as int

    Returns:
      None

    Raises:
      urllib2.HTTPError on non-200 response.
    """
    assert package_name
    assert isinstance(package_version, int)

    path = '/packages/%s.%d' % (package_name, package_version)
    url = FLAGS.mrtaskman_server + path
    body = None
    headers = {}
    request = urllib2.Request(url, body, headers)
    request.get_method = lambda: 'DELETE'

    response = urllib2.urlopen(request)
    response.read()
    return
