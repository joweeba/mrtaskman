#!/usr/bin/python

"""Executes Android Monkey stress test over adb to attached Android device."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

import json
import logging
import os
import subprocess
import sys
import time

from tasklib import apklib

ADB_COMMAND = apklib.ADB_COMMAND
MONKEY_COMMAND = ADB_COMMAND + 'shell "/system/bin/monkey -p %s --kill-process-after-error -v 5000 --pct-touch 10 --pct-trackball 90 -s 10 %s; echo $? > /data/local/tmp/ret"'


def ExitWithErrorCode(error_code):
  if error_code == 0:
    logging.warning('Error code is zero, maaking it non-zero')
    error_code = -7
  sys.exit(error_code)


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
    class_path = apklib.FindClassPath(manifest)
    apklib.WriteResultMetadata(manifest)
    logging.info('Found class_path: %s', class_path)

    logging.info('Installing .apk...')
    try:
      output = subprocess.check_output(
          ADB_COMMAND + 'install -r %s' % apk_file_path,
          shell=True)
      apklib.CheckAdbSuccess(output)
    except subprocess.CalledProcessError, e:
      logging.error('adb install error %d:\n%s', e.returncode, e.output)
      ExitWithErrorCode(e.returncode)

    try:
      logging.info('Running command...')
      try:
        subprocess.check_call(MONKEY_COMMAND % (class_path, ' '.join(argv)),
                              stdout=sys.stdout,
                              stderr=sys.stderr,
                              shell=True)
        apklib.CheckAdbShellExitCode()
      except subprocess.CalledProcessError, e:
        logging.error('Error %d:\n%s', e.returncode, e.output)
        ExitWithErrorCode(e.returncode)
    finally:
      logging.info('Uninstalling .apk...')
      try:
        output = subprocess.check_output(
            ADB_COMMAND + 'uninstall %s' % class_path,
            shell=True)
        apklib.CheckAdbSuccess(output)
      except subprocess.CalledProcessError, e:
        logging.error('adb uninstall error %d:\n%s', e.returncode, e.output)
        ExitWithErrorCode(e.returncode)

    logging.info('Monkey work done successfully.')
    return 0
  finally:
    logging.shutdown()


if __name__ == '__main__':
  main(sys.argv)
