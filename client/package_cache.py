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

"""MrTaskman package cache for MacOS X.

Attempts to download packages at most once per worker machine.
"""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

import datetime
import json
import logging
import os
import subprocess
import sys
import time
import urllib2
import warnings

from third_party import portalocker


class Error(Exception):
  pass


class InvalidPackageError(Error):
  pass


def ValidatePackageInfo(package_info):
  if not 'name' in package_info:
    raise InvalidPackageError('name field is required.')
  if not 'version' in package_info:
    raise InvalidPackageError('version field is required.')
  if not isinstance(package_info['version'], int):
    raise InvalidPackageError('version field must be an int.')


def VerifyDirectoryExists(directory):
  return os.path.isdir(directory)


def GetDirectorySize(start_path):
  total_size = 0
  for dirpath, dirnames, filenames in os.walk(start_path):
    for f in filenames:
      fp = os.path.join(dirpath, f)
      total_size += os.path.getsize(fp)
  return total_size


def MakePackageString(package_name, package_version):
  return '%s^^^%d' % (package_name, package_version)


def SecondsSinceEpoch():
  """Returns number of seconds since the Epoch as int."""
  return int(datetime.datetime.now().strftime('%s'))


class PackageCache(object):
  def __init__(self,
               min_duration_seconds,
               max_size_bytes,
               root_path,
               low_watermark_percentage=0.6,
               high_watermark_percentage=0.8):
    """Connects to an existing cache on disk or creates a new one at root_path.

    Args:
      max_size_bytes: Maximum size of cache on disk
      min_duration_seconds: Minimum time to keep files in cache before deleting
      root_path: Location of cache on disk
      low_watermark_percentage: [0-1] float percentage not to delete below.
      high_watermark_percentage: [0-1] float percentage to at least delete to.
    """
    warnings.filterwarnings('ignore', 'tempnam is a potential security risk')
    self._locked = False
    self._lock = None
    self.max_size_bytes = int(max_size_bytes)
    self.min_duration_seconds = int(min_duration_seconds)
    self.root_path = root_path
    self.low_watermark_percentage = float(low_watermark_percentage)
    self.high_watermark_percentage = float(high_watermark_percentage)

    assert self.low_watermark_percentage >= 0.0
    assert self.high_watermark_percentage > self.low_watermark_percentage
    assert self.max_size_bytes >= 0
    assert self.min_duration_seconds >= 0
    self._TryCreateCache()

  def _Lock(self):
    """Acquires an exclusive lock on the cache control files.

    Should be called within try: finally: clause with _Unlock to prevent
    bad juju.
    """
    self._lock = open(os.path.join(self.root_path, '.cache_info'), 'r+')
    portalocker.lock(self._lock, portalocker.LOCK_EX)
    self._locked = True

  def _Unlock(self):
    """Releases the lock acquired by _Lock."""
    portalocker.unlock(self._lock)
    self._lock.close()
    self._locked = False

  def IsLocked(self):
    return self._locked

  def _TryCreateCache(self):
    """Blocks until cache is created, creating cache if necessary.

    First process locks and writes cache files if they do not exist.
    Other processes block until cache files are created.
    Called in __init__ so that class instances are always valid.
    """
    os.system('mkdir -p "%s"' % self.root_path)
    try:
      lockfile_path = os.path.join(self.root_path, 'lockfile')
      os.system('lockfile %s' % lockfile_path)

      try:
        root_file = open(os.path.join(self.root_path, '.cache_info'), 'r+')
        root_file.close()
        logging.info('Connecting to established cache at %s', self.root_path)
      except IOError, e:
        if e.errno == 2:
          logging.info('Creating cache at %s', self.root_path)
          self._CreateCacheFiles()
    except:
      os.system('rm -rf %s' % self.root_path)
      raise
    finally:
      try:
        os.system('rm -f %s' % lockfile_path)
      except:
        pass

  def _CreateCacheFiles(self):
    """Called within lockfile of _TryCreateCache once per cache."""
    # Write .cache_info file.
    contents = {
      'max_size_bytes': self.max_size_bytes,
      'min_duration_seconds': self.min_duration_seconds,
      'low_watermark_percentage': self.low_watermark_percentage,
      'high_watermark_percentage': self.high_watermark_percentage,
    }
    self._CreateCacheFile('.cache_info', json.dumps(contents, indent=2))

    # Create remaining files with empty representations.
    self._CreateCacheFile('.index', json.dumps({}))
    self._CreateCacheFile('.copying', json.dumps({}))
    self._CreateCacheFile('.downloading', json.dumps({}))
    self._CreateCacheFile('.deleting', json.dumps({}))

  def _CreateCacheFile(self, filename, data):
    f = open(os.path.join(self.root_path, filename), 'w')
    f.write(data)
    f.flush()
    f.close()

  def _ReadCacheFile(self, filename):
    f = open(os.path.join(self.root_path, filename), 'r+')
    data = f.read()
    f.close()
    return json.loads(data)

  def _UpdateIndexTimestamp(self, package_string):
    assert self.IsLocked()
    data = self._ReadCacheFile('.index')
    data[package_string]['timestamp'] = SecondsSinceEpoch()
    index = open(os.path.join(self.root_path, '.index'), 'w')
    json.dump(data, index, indent=2)
    index.flush()
    index.close()

  def _CopyDirectory(self, from_dir, to_dir):
    """Copies entire contents of from_dir to to_dir."""
    os.system('cp -Rf %s/ %s' % (from_dir, to_dir))

  def _AddToCopying(self, package_string):
    """Modifies the .copying file to mark the current as copying."""
    assert self.IsLocked()
    record = {
      'pid': os.getpid(),
      'timestamp': SecondsSinceEpoch(),
    }
    copying = open(os.path.join(self.root_path, '.copying'), 'r')
    records = json.load(copying)
    copying.close()
    if package_string in records:
      records[package_string].append(record)
    else:
      records[package_string] = [record]
    copying = open(os.path.join(self.root_path, '.copying'), 'w')
    json.dump(records, copying, indent=2)
    copying.flush()
    copying.close()

  def _RemoveFromCopying(self, package_string):
    """Modifies the .copying file to remove the given entry."""
    assert self.IsLocked()
    copying = open(os.path.join(self.root_path, '.copying'), 'r')
    records = json.load(copying)
    copying.close()
    record = records.pop(package_string, None)
    assert record
    pid = os.getpid()
    new_record = []
    for rec in record:
      if rec['pid'] != pid:
        new_record.append(rec)
    if new_record:
      records[package_string] = new_record

    copying = open(os.path.join(self.root_path, '.copying'), 'w')
    json.dump(records, copying, indent=2)
    copying.flush()
    copying.close()

  def _AddToDownloading(self, package_string, directory):
    """Modifies the .downloading file to mark the current as downloading."""
    assert self.IsLocked()
    record = {
      'pid': os.getpid(),
      'directory': directory,
      'timestamp': SecondsSinceEpoch(),
    }
    downloading = open(os.path.join(self.root_path, '.downloading'), 'r')
    records = json.load(downloading)
    downloading.close()
    records[package_string] = record
    downloading = open(os.path.join(self.root_path, '.downloading'), 'w')
    json.dump(records, downloading, indent=2)
    downloading.flush()
    downloading.close()

  def _RemoveFromDownloading(self, package_string):
    """Modifies the .downloading file to remove the given entry."""
    assert self.IsLocked()
    downloading = open(os.path.join(self.root_path, '.downloading'), 'r')
    records = json.load(downloading)
    downloading.close()
    records.pop(package_string, None)
    downloading = open(os.path.join(self.root_path, '.downloading'), 'w')
    json.dump(records, downloading, indent=2)
    downloading.flush()
    downloading.close()

  def _IsAlreadyDownloading(self, package_string):
    """Determines if package is already being downloaded by another process."""
    assert self.IsLocked()
    downloading = open(os.path.join(self.root_path, '.downloading'), 'r')
    records = json.load(downloading)
    downloading.close()
    record = records.pop(package_string, None)
    if record is not None:
      # Timeout downloads after 5 minutes.
      if record['pid'] == os.getpid():
        # Thread-safety issue: multiple threads in same process re-download.
        return  False
      if SecondsSinceEpoch() - record['timestamp'] < 5*60:
        return True
    return False

  def _AddToIndex(self, package_string, cache_dir):
    """Modifies the .index file by adding an entry for package_string."""
    assert self.IsLocked()
    dir_size = GetDirectorySize(cache_dir)
    record = {
      'pid': os.getpid(),
      'cache_dir': cache_dir,
      'timestamp': SecondsSinceEpoch(),
      'size_bytes': dir_size,
    }
    index = open(os.path.join(self.root_path, '.index'), 'r')
    records = json.load(index)
    index.close()

    total_size = records.get('total_size', 0)
    new_total_size = total_size
    if total_size + dir_size > self.max_size_bytes:
      logging.info('Need to do some clean up.')
      (delete_list, new_total_size) = self._GetDeleteList(records)
      deleted_records = [records.pop(deleted) for deleted in delete_list]
      os.system('rm -rf %s' % ' '.join(
          [rec['cache_dir'] for rec in deleted_records]))
      logging.info('deleted %d bytes', total_size - new_total_size)

    records[package_string] = record
    records['total_size'] = new_total_size + dir_size
    logging.info('new total_size: %d', records['total_size'])

    index = open(os.path.join(self.root_path, '.index'), 'w')
    json.dump(records, index, indent=2)
    index.flush()
    index.close()

  def _GetDeleteList(self, records):
    seconds_since_epoch = SecondsSinceEpoch()
    record_list = []
    total_size = 0
    for (package_string, record) in records.iteritems():
      if package_string == 'total_size':
        total_size = record
        continue
      if seconds_since_epoch - record['timestamp'] < self.min_duration_seconds:
        continue
      record_list.append((package_string,
                          record['timestamp'],
                          record['size_bytes']))
    record_list.sort(key=lambda x:x[1])
    assert total_size > 0

    delete_list = []
    low_watermark = self.low_watermark_percentage * self.max_size_bytes
    for record in record_list:
      if len(delete_list) > 0 and (
            total_size - record[2] < low_watermark):
        break
      delete_list.append(record[0])
      total_size -= record[2]
    return (delete_list, total_size)

  def _RemoveFromIndex(self, package_string):
    """Modifies the .index file to remove the given entry."""
    assert self.IsLocked()
    index = open(os.path.join(self.root_path, '.index'), 'r')
    records = json.load(index)
    index.close()
    records.pop(package_string, None)
    index = open(os.path.join(self.root_path, '.index'), 'w')
    json.dump(records, index, indent=2)
    index.flush()
    index.close()

  def CopyToDirectory(self, package_info, directory, on_cache_miss):
    """Copies package files to given directory, downloading if necessary.

    Args:
      package_info: dict containing 'name', 'version', and 'url'.
      directory: path to copy to as str.
      on_cache_miss: Callable accepting
          (package_name, package_version, directory).

    Raises:
      InvalidPackageError on invalid package_info.
    """
    ValidatePackageInfo(package_info)
    VerifyDirectoryExists(directory)

    found_in_index = False
    is_already_downloading = False
    package_string = MakePackageString(package_info['name'],
                                       package_info['version'])

    self._Lock()
    try:
      index = self._ReadCacheFile('.index')
      if package_string in index:
        found_in_index = True
        cache_dir = index[package_string]['cache_dir']
        self._UpdateIndexTimestamp(package_string)
        self._AddToCopying(package_string)
      else:
        if self._IsAlreadyDownloading(package_string):
          logging.info('%s is already downloading. Waiting.', package_string)
          is_already_downloading = True
        else:
          cache_dir = os.tempnam(self.root_path, package_string)
          self._AddToDownloading(package_string, cache_dir)
    finally:
      self._Unlock()

    if found_in_index:
      logging.info('Cache hit. Copying from %s to %s', cache_dir, directory)
      start_time = datetime.datetime.now()
      self._CopyDirectory(cache_dir, directory)
      timedelta = datetime.datetime.now() - start_time
      self._Lock()
      try:
        self._RemoveFromCopying(package_string)
      finally:
        self._Unlock()
      logging.info('Copied in %0.3f seconds',
                   timedelta.seconds +
                   float(timedelta.microseconds) / 1000000)
    else:
      if is_already_downloading:
        self._Lock()
        try:
          while self._IsAlreadyDownloading(package_string):
            self._Unlock()
            logging.info('Still waiting for %s to download.', package_string)
            time.sleep(10.0)
            self._Lock()
        finally:
          self._Unlock()
        # Recurse and allow logic above to perform copy, or re-download.
        return self.CopyToDirectory(package_info, directory, on_cache_miss)
      else:
        # TODO(jeff.carollo): This potentially leaves partially-downloaded
        # directories in the cache directory, but not in the .index. Will
        # need to build a clean-up cache.
        logging.info('Cache miss. Downloading to %s', cache_dir)
        os.system('mkdir -p %s' % cache_dir)
        start_time = datetime.datetime.now()
        on_cache_miss(package_info['name'], package_info['version'], cache_dir)
        timedelta = datetime.datetime.now() - start_time

        logging.info('Download completed in %0.3f seconds. '
                     'Copying from %s to %s',
                     timedelta.seconds +
                     float(timedelta.microseconds) / 1000000,
                     cache_dir, directory)
        start_time = datetime.datetime.now()
        self._CopyDirectory(cache_dir, directory)
        timedelta = datetime.datetime.now() - start_time
        self._Lock()
        try:
          self._AddToIndex(package_string, cache_dir)
          self._RemoveFromDownloading(package_string)
        finally:
          self._Unlock()
        logging.info('Copied into cache in %0.3f seconds',
                     timedelta.seconds +
                     float(timedelta.microseconds) / 1000000)

  def InvalidatePackageCache(self, package_info):
    """Marks given package as invalid, forcing a redownload on next access.

    Raises:
      InvalidPackageError on invalid package_info.
    """
    ValidatePackageInfo(package_info)
    raise NotImplementedError()

  def RefreshCache(self, package_info):
    """Calls InvalidPackageCache followed by dummy read to force redownload.

    Raises:
      InvalidPackageError on invalid package_info.
    """
    ValidatePackageInfo(package_info)
    raise NotImplementedError()


def main(argv):
  # Set up logging.
  FORMAT = '%(asctime)-15s %(message)s'
  logging.basicConfig(format=FORMAT, level=logging.INFO)


if __name__ == '__main__':
  main(sys.argv)
