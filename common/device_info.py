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

"""Provides info about an attached device depending on environment variables.

Expects that DEVICE_SN will be set in process environment.
"""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

import os


DEVICE_INFO = {
    '0146A14C1001800C': {
        'device_type': 'phone',
        'device_name': 'Galaxy Nexus',
        'os_name': 'android',
        'os_version': '4.0.2',
        'cell_number': '4258900342',
        'provider': 'Verizon Wireless',
        'hub': '01',
        'hub_port': 'D'
    },
    'HT16RS015741': {
        'device_type': 'phone',
        'device_name': 'HTC Thunderbolt',
        'os_name': 'android',
        'os_version': '2.3.4',
        'cell_number': '4258908379',
        'provider': 'Verizon Wireless',
        'hub': '01',
        'hub_port': 'B'
    },
    'TA08200CI0': {
        'device_type': 'phone',
        'device_name': 'Motorola Droid X2',
        'os_name': 'android',
        'os_version': '2.3.4',
        'cell_number': '4258909336',
        'provider': 'Verizon Wireless',
        'hub': '01',
        'hub_port': 'A'
    },
    '388920443A07097': {
        'device_type': 'tablet',
        'device_name': 'Samsung Galaxy Tab',
        'os_name': 'android',
        'os_version': '3.2',
        'provider': 'Verizon Wireless',
        'hub': '01',
        'hub_port': 'C'
    }
}


# Shouldn't change for the life of this process.
DEVICE_SN = os.environ.get('DEVICE_SN', None)


def GetDeviceSerialNumber():
  """Returns the serial number of the device assigned to the current worker.

  Pulls from environment variables.

  Returns:
    Serial number as str, or None.
  """
  return DEVICE_SN


def GetDeviceInfo(device_sn=DEVICE_SN):
  """Retrieves device info from given device serial number."""
  return DEVICE_INFO.get(device_sn, None)


def AppendIf(l, value):
  """Appends to a list if value evaluates to a boolean."""
  if value:
    l.append(value)


def GetCapabilities():
  """Returns a list of capabilities of device from environment or None."""
  capabilities = []
  if DEVICE_SN:
    capabilities.append(DEVICE_SN)
    device_info = GetDeviceInfo()
    if device_info:
      AppendIf(capabilities, device_info.get('device_name', None))
      AppendIf(capabilities, device_info.get('device_type', None))
      AppendIf(capabilities, device_info.get('os_name', None))
      AppendIf(capabilities, device_info.get('os_version', None))
      AppendIf(capabilities, device_info.get('provider', None))
  return capabilities
