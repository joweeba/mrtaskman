#!/usr/bin/python
"""Tests of package_cache."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

import json
import logging
import os
import threading
import time
import unittest

from client import package_cache

class PackageCacheTest(unittest.TestCase):
  def setUp(self):
    self.path = '/tmp/cache_test'
    self.min_duration_seconds = 0
    self.max_size_bytes = 100 * 1024
    self.low_watermark_percentage = 0.6
    self.high_watermark_percentage = 0.8

    # Clear old cache, if any.
    os.system('rm -rf %s' % self.path)
    self.cache = package_cache.PackageCache(
        self.min_duration_seconds,
        self.max_size_bytes,
        self.path,
        self.low_watermark_percentage,
        self.high_watermark_percentage)

  def tearDown(self):
    os.system('rm -rf %s' % self.path)

  def tearDownTestCase(self):
    os.system('rm -rf %s' % self.path)

  def testSetUpAndTearDown(self):
    logging.info('setUp done. tearing down...')

  def testDotCacheInfoMatchesSettings(self):
    dot_cache_info_file = open(os.path.join(self.path, '.cache_info'))
    cache_info = json.load(dot_cache_info_file)
    self.assertEqual(cache_info['min_duration_seconds'],
                     self.min_duration_seconds)
    self.assertEqual(cache_info['max_size_bytes'], self.max_size_bytes)
    self.assertEqual(cache_info['low_watermark_percentage'],
                     self.low_watermark_percentage)
    self.assertEqual(cache_info['high_watermark_percentage'],
                     self.high_watermark_percentage)

  def testSecondCacheClientDoesNotTrampleCacheInfoFile(self):
    second_cache = package_cache.PackageCache(
        20, 100, self.path, self.low_watermark_percentage,
        self.high_watermark_percentage)
    self.testDotCacheInfoMatchesSettings()

  def testSecondCacheClientObeysLock(self):
    second_cache = package_cache.PackageCache(
        20, 100, self.path, self.low_watermark_percentage,
        self.high_watermark_percentage)

    # Acquire lock via first cache.
    self.cache._Lock()

    event = threading.Event()

    def DoSecondThread(second_cache, event):
      second_cache._Lock()
      second_cache._Unlock()
      event.set()

    # Tell second cache to attempt to acquire the lock (should block.)
    second_thread = threading.Thread(target=DoSecondThread,
                                     args=(second_cache, event))
    second_thread.start()

    self.assertFalse(event.is_set())
    time.sleep(0.5)
    self.assertFalse(event.is_set())

    # Release the lock and expect first thread to finish.
    self.cache._Unlock()
    self.assertTrue(event.wait(10.0))
    second_thread.join(10.0)

  def testCopyToDirectory_NeedsDownload(self):
    name = 'name'
    version = 1
    tmp_dir = os.tempnam('/tmp', 'testCopyToDirectory_NeedsDownload')

    def MockOnCacheMiss(n, v, p):
      self.assertEqual(name, n)
      self.assertEqual(version, v)

    try:
      os.system('mkdir -p %s' % tmp_dir)
      self.cache.CopyToDirectory(
          {
            'name': name,
            'version': version,
          },
          tmp_dir,
          MockOnCacheMiss)
    finally:
      os.system('rm -rf %s' % tmp_dir)

  def testAddToDownloading(self):
    name = 'name'
    version = 1
    tmp_dir = os.tempnam('/tmp', 'testCopyToDirectory_NeedsDownload')
    pid = os.getpid()

    def MockOnCacheMiss(n, v, p):
      self.assertEqual(name, n)
      self.assertEqual(version, v)

      downloading = open(os.path.join(self.path, '.downloading'), 'r')
      records = json.load(downloading)
      downloading.close()

      record = records[package_cache.MakePackageString(name, version)]
      self.assertEqual(pid, record['pid'])
      self.assertTrue(record['timestamp'] <= time.mktime(time.gmtime()))

    try:
      os.system('mkdir -p %s' % tmp_dir)
      self.cache.CopyToDirectory(
          {
            'name': name,
            'version': version,
          },
          tmp_dir,
          MockOnCacheMiss)
    finally:
      os.system('rm -rf %s' % tmp_dir)

  def testRemoveFromDownloading(self):
    name = 'name'
    version = 1
    tmp_dir = os.tempnam('/tmp', 'testCopyToDirectory_NeedsDownload')
    pid = os.getpid()

    def MockOnCacheMiss(n, v, p):
      self.assertEqual(name, n)
      self.assertEqual(version, v)

      downloading = open(os.path.join(self.path, '.downloading'), 'r')
      records = json.load(downloading)
      downloading.close()

      record = records[package_cache.MakePackageString(name, version)]
      self.assertEqual(pid, record['pid'])
      self.assertTrue(record['timestamp'] <= time.mktime(time.gmtime()))

    try:
      os.system('mkdir -p %s' % tmp_dir)
      self.cache.CopyToDirectory(
          {
            'name': name,
            'version': version,
          },
          tmp_dir,
          MockOnCacheMiss)
    finally:
      os.system('rm -rf %s' % tmp_dir)

    downloading = open(os.path.join(self.path, '.downloading'), 'r')
    records = json.load(downloading)
    downloading.close()

    record = records.get(package_cache.MakePackageString(name, version), None)
    self.assertIsNone(record)

  def testRemoveFromIndex(self):
    name = 'name'
    version = 1
    tmp_dir = os.tempnam('/tmp', 'testCopyToDirectory_NeedsDownload')
    pid = os.getpid()

    def MockOnCacheMiss(n, v, p):
      self.assertEqual(name, n)
      self.assertEqual(version, v)

    try:
      os.system('mkdir -p %s' % tmp_dir)
      self.cache.CopyToDirectory(
          {
            'name': name,
            'version': version,
          },
          tmp_dir,
          MockOnCacheMiss)
    finally:
      os.system('rm -rf %s' % tmp_dir)

    index = open(os.path.join(self.path, '.index'), 'r')
    records = json.load(index)
    index.close()

    record = records[package_cache.MakePackageString(name, version)]
    self.assertEqual(pid, record['pid'])
    self.assertNotEqual(tmp_dir, record['cache_dir'])
    self.assertTrue(self.path in record['cache_dir'])
    self.assertTrue(record['timestamp'] <= time.mktime(time.gmtime()))
    self.assertEqual(0, record['size_bytes'])

    self.cache._Lock()
    self.cache._RemoveFromIndex(package_cache.MakePackageString(name, version))
    self.cache._Unlock()
    index = open(os.path.join(self.path, '.index'), 'r')
    records = json.load(index)
    index.close()

    record = records.get(package_cache.MakePackageString(name, version), None)
    self.assertIsNone(record)

  def testWaitOnDownload(self):
    name = 'name'
    version = 1
    tmp_dir = os.tempnam('/tmp', 'testWaitOnDownload')
    tmp_dir2 = os.tempnam('/tmp', 'testWaitOnDownload2')
    os.system('mkdir -p %s' % tmp_dir)
    os.system('mkdir -p %s' % tmp_dir2)

    second_cache = package_cache.PackageCache(
        20, 100, self.path, self.low_watermark_percentage,
        self.high_watermark_percentage)

    event = threading.Event()

    def DoSecondThread(second_cache, event):
      try:
        # Should block.
        second_cache.CopyToDirectory({'name': name, 'version': version},
                                     tmp_dir2, None)
      finally:
        event.set()

    # Tell second cache to attempt to acquire the lock (should block.)
    second_thread = threading.Thread(target=DoSecondThread,
                                     args=(second_cache, event))

    def MockOnCacheMiss(n, v, p):
      self.assertEqual(name, n)
      self.assertEqual(version, v)
      os.system('echo "nothing" > %s' % os.path.join(p, 'file.txt'))

      second_thread.start()
      time.sleep(1.5)

    try:
      self.cache.CopyToDirectory(
          {
            'name': name,
            'version': version,
          },
          tmp_dir,
          MockOnCacheMiss)
    finally:
      event.wait()
      filename = os.path.join(tmp_dir2, 'file.txt')
      try:
        with open(filename): pass
      except IOError:
        self.fail('%s did not exist' % filename)
      os.system('rm -rf %s' % tmp_dir)
      os.system('rm -rf %s' % tmp_dir2)


# TODO(jeff.carollo): testCopyDirectory.


def main():
  # Set up logging.
  FORMAT = '%(asctime)-15s %(message)s'
  logging.basicConfig(format=FORMAT, level=logging.INFO)
  unittest.main()


if __name__ == '__main__':
  main()
