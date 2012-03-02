#!/usr/bin/python

"""Executes Android Launch test over adb to attached Android device."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

import logging
import os
import subprocess
import sys
import time

from tasklib import apklib


ADB_COMMAND = apklib.ADB_COMMAND
LAUNCH_COMMAND = (ADB_COMMAND +
    'shell "am start -S %s/%s; echo $? > /mnt/sdcard/ret"')

STDOUT_FILENAME = 'cmd_stdout.log'
STDERR_FILENAME = 'cmd_stderr.log'


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
    apklib.WriteResultMetadata(manifest)
    class_path = apklib.FindClassPath(manifest)
    class_name = apklib.FindClassName(manifest)
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
      logging.info('Running command %s.',
          LAUNCH_COMMAND % (class_path, class_name))
      cmd_stdout = open(STDOUT_FILENAME, 'w')
      cmd_stderr = open(STDERR_FILENAME, 'w')
      try:
        subprocess.check_call(LAUNCH_COMMAND % (class_path, class_name),
                              stdout=sys.stdout,
                              stderr=sys.stderr,
                              shell=True)
        apklib.CheckAdbShellExitCode()
      except subprocess.CalledProcessError, e:
        logging.error('CalledProcessError %d:\n%s', e.returncode, e.output)
        ExitWithErrorCode(e.returncode)
    finally:
      md_stdout.flus()
      cmd_stdout.close()
      cmd_stderr.flush()
      cmd_stderr.close()
      logging.info('Uninstalling .apk...')
      try:
        output = subprocess.check_output(
            ADB_COMMAND + 'uninstall %s' % class_path,
            shell=True)
        apklib.CheckAdbSuccess(output)
      except subprocess.CalledProcessError, e:
        logging.error('adb uninstall error %d:\n%s', e.returncode, e.output)
        ExitWithErrorCode(e.returncode)

      # Inspect and dump to logs the cmd stdout output.
      cmd_stdout = open(STDOUT_FILENAME, 'r')
      stdout_exitcode = apklib.DupAndCheckErrorLogs(cmd_stdout, sys.stdout)

      # Inspect and dump to logs the cmd stderr output.
      cmd_stderr = open(STDERR_FILENAME, 'r')
      stderr_exitcode = apklib.DupAndCheckErrorLogs(cmd_stderr, sys.stderr)

      if cmd_stdout > 0:
        ExitWithErrorCode(cmd_stdout)
      if stderr_exitcode > 0:
        ExitWithErrorCode(stderr_exitcode)
    logging.info('Launch work done successfully.')
    return 0
  finally:
    logging.shutdown()


if __name__ == '__main__':
  main(sys.argv)
