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
    class_path = apklib.FindClassPath(manifest)
    apklib.WriteResultMetadata(manifest)
    logging.info('Found class_path: %s', class_path)

    logging.info('Signing .apk...')
    apklib.SignApk(apk_file_path)

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
      cmd_stdout = open(STDOUT_FILENAME, 'w')
      cmd_stderr = open(STDERR_FILENAME, 'w')
      try:
        subprocess.check_call(MONKEY_COMMAND % (class_path, ' '.join(argv)),
                              stdout=cmd_stdout,
                              stderr=cmd_stderr,
                              shell=True)
        apklib.CheckAdbShellExitCode()
      except subprocess.CalledProcessError, e:
        logging.error('Error %d:\n%s', e.returncode, e.output)
        ExitWithErrorCode(e.returncode)
    finally:
      cmd_stdout.flush()
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

      try:
        # Inspect and dump to logs the cmd stdout output.
        cmd_stdout = open(STDOUT_FILENAME, 'r')
        stdout_exitcode = apklib.DumpAndCheckErrorLogs(cmd_stdout, sys.stdout)
      except Exception, e:
        logging.error('Error while dumping command stdout: %s', str(e))
        stdout_exitcode = -5  # Don't exit yet, allow stderr to be dumped.
      finally:
        cmd_stdout.close()

      try:
        # Inspect and dump to logs the cmd stderr output.
        cmd_stderr = open(STDERR_FILENAME, 'r')
        stderr_exitcode = apklib.DumpAndCheckErrorLogs(cmd_stderr, sys.stderr)
      except Exception, e:
        logging.error('Error while dumping command stderr: %s', str(e))
        stderr_exitcode = -5
      finally:
        cmd_stderr.close()

      if stdout_exitcode != 0:
        logging.info('Error found in stdout.')
        ExitWithErrorCode(stdout_exitcode)
      if stderr_exitcode != 0:
        logging.info('Error found in stderr.')
        ExitWithErrorCode(stderr_exitcode)

    logging.info('Monkey work done successfully.')
    return 0
  finally:
    logging.shutdown()


if __name__ == '__main__':
  main(sys.argv)
