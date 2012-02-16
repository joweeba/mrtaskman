#!/usr/bin/python

"""Executes Android Install test over adb to attached Android device."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

import logging
import os
import subprocess
import sys
import time

from tasklib import apklib


ADB_COMMAND = apklib.ADB_COMMAND


def main(argv):
  my_name = argv.pop(0)

  try:
    apk_file_path = argv.pop(0)
  except:
    sys.stderr.write('Must give apk_file_path as first argument.\n')
    sys.exit(-1)

  FORMAT = '%(asctime)-15s %(message)s'
  logging.basicConfig(format=FORMAT, level=logging.DEBUG)

  try:
    manifest = apklib.ReadAndroidManifest(apk_file_path)
    apklib.WriteResultMetadata(manifest)
    class_path = apklib.FindClassPath(manifest)
    logging.info('Found class_path: %s', class_path)

    logging.info('Installing .apk...')
    try:
      output = subprocess.check_output(
          ADB_COMMAND + 'install -r %s' % apk_file_path,
          shell=True)
      apklib.CheckAdbSuccess(output)
    except subprocess.CalledProcessError, e:
      logging.error('adb install error %d:\n%s', e.returncode, e.output)
      sys.exit(e.returncode)

    logging.info('Uninstalling .apk...')
    try:
      output = subprocess.check_output(
          ADB_COMMAND + 'uninstall %s' % class_path,
          shell=True)
      apklib.CheckAdbSuccess(output)
    except subprocess.CalledProcessError, e:
      logging.error('adb uninstall error %d:\n%s', e.returncode, e.output)
      sys.exit(e.returncode)
  
    logging.info('Install work done successfully.')
    return 0
  finally:
    logging.shutdown()


if __name__ == '__main__':
  main(sys.argv)
