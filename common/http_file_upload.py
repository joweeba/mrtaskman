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

"""Allows HTTP upload to AppEngine forms which contain files.

Currently does not make use of HTTP streaming, or file streaming.
TODO(jeff.carollo): Add file and http stream support.
"""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

import logging
import urllib
import urlparse
import urllib2


def SendMultipartHttpFormData(url, method, headers, form_data, file_data):
  """Sends form data and files as HTTP multipart/form-data.

  Example:
    SendMultipartHttpFormData(
        'http://www.example.com/form/addfiles',
        'POST',
        {'Cookie': 'sad;fkj239jskfjsadf'},
        [{'name': 'field1',
          'data': 'value1'},
         {'name': 'field2',
          'data': 'value2'}],
        [{'name': 'file_field_1',
          'filename': 'foo.txt',
          'data': 'file_data'},
         {'name': 'file_field_2',
          'filename': 'bar.txt',
          'filepath': '/usr/local/bar.txt'}])

  Args:
    url: Full url as str.
    method: 'POST', 'PUT', etc as str.
    headers: Dict of {'header-name': 'header-value'} pairs.
    form_data: List of {'name': name, 'data': data} pairs.
    file_data: List of {'name': name, 'filename': filename, 'data': data}
               or {'name': name, 'filename': filename, 'filepath': filepath}.
  
  Returns:
    urllib2.Response object. obj.code gives HTTP code. obj.read() has data.
  """
  BOUNDARY = u'------FORM_BOUNDARY--------'

  headers['Content-Type'] = u'multipart/form-data; boundary=%s' % BOUNDARY
  BOUNDARY = u'--%s' % BOUNDARY
  body_parts = []

  # Add non-file pieces.
  for form_piece in form_data:
    try:
      body_parts.append(BOUNDARY)
      body_parts.append(
          u'Content-Disposition: form-data; name="%s"' % form_piece['name'])
      try:
        body_parts.append(u'Content-Type: %s' % form_piece['Content-Type'])
      except:
        body_parts.append(u'Content-Type: text/plain; charset=utf-8')
      body_parts.append(u'')
      body_parts.append(form_piece['data'].encode('utf-8'))
    except KeyError:
      logging.error('form_data dicts must contain "name" and "data" fields.')
      raise

  # Add file pieces.
  for file_piece in file_data:
    try:
      body_parts.append(BOUNDARY)
      body_parts.append(
          u'Content-Disposition: form-data; name="%s"; filename="%s"' %
          (file_piece['name'], file_piece['filename']))
      body_parts.append(u'Content-Type: application/octet-stream')
      body_parts.append(u'')
      try:
        data = file_piece['data']
      except KeyError:
        data = file(file_piece['filepath'], 'r').read()
      body_parts.append(data.encode('utf-8'))
    except KeyError:
      logging.error('file_data pieces must contain "name" and "filename" ' +
                    'fields and either a "data" or "filepath" field.')
      raise

  # Terminate correctly.
  body_parts.append(BOUNDARY)
  body_parts.append(u'')

  body = u'\r\n'.join(body_parts)

  request = urllib2.Request(url, body, headers)
  request.method = method

  response = urllib2.urlopen(request)
  return response
