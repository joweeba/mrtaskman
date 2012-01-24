#!/usr/bin/python

"""Executes Android Monkey stress test over adb to attached Android device."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

import logging
import os
import subprocess
import sys
import time


def RunShellCommand(command):
  try:
    subprocess.check_call(command,
                          stdout=sys.stdout,
                          stderr=sys.stderr,
                          shell=True)
  except subprocess.CalledProcessError, e:
    logging.error('Error %d:\n%s', e.returncode, e.output)
    sys.exit(e.returncode)


def ReadAndroidManifest(android_manifest_path):
  try:
    output = subprocess.check_output(
        'java -jar AXMLPrinter2.jar %s' % android_manifest_path,
        shell=True)
    return output
  except subprocess.CalledProcessError, e:
    logging.error('AXMLPrinter2 error %d:\n%s', e.returncode, e.output)
    sys.exit(e.returncode)


def FindClassPath(apk_file_path):
  APK_UNPACKED_DIR = '__apk_unpacked__'
  RunShellCommand('unzip %s -d %s' % (apk_file_path, APK_UNPACKED_DIR))
  manifest_path = os.path.join(APK_UNPACKED_DIR, 'AndroidManifest.xml')
  manifest = ReadAndroidManifest(manifest_path)

  package_begin = manifest.find('package')
  if package_begin < 0:
    logging.fatal('No package begin.')
  package_begin += 7

  open_quote = manifest.find('"', package_begin)
  if open_quote < 0:
    logging.fatal('No open quote.')
  open_quote += 1

  close_quote = manifest.find('"', open_quote)
  if close_quote < 0:
    logging.fatal('No close quote.')
  return manifest[open_quote:close_quote]


def CheckAdbSuccess(adb_output):
  """Cover the fail."""
  if 'Success' in adb_output:
    return
  adb_output.returncode = -5
  raise subprocess.CalledProcessError(-1, 'adb', output=adb_output)


MONKEY_COMMAND = 'adb shell /system/bin/monkey -p %s --kill-process-after-error -v 1000 --pct-touch 10 --pct-trackball 90 -s 10 %s'


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
    class_path = FindClassPath(apk_file_path)
    logging.info('Found class_path: %s', class_path)

    logging.info('Installing .apk...')
    try:
      output = subprocess.check_output('adb install -r %s' % apk_file_path,
                                       shell=True)
      CheckAdbSuccess(output)
    except subprocess.CalledProcessError, e:
      logging.error('adb install error %d:\n%s', e.returncode, e.output)
      sys.exit(e.returncode)

    try:
      logging.info('Running command...')
      try:
        subprocess.check_call(MONKEY_COMMAND % (class_path, ' '.join(argv)),
                              stdout=sys.stdout,
                              stderr=sys.stderr,
                              shell=True)
      except subprocess.CalledProcessError, e:
        logging.error('Error %d:\n%s', e.returncode, e.output)
        sys.exit(e.returncode)
    finally:
      logging.info('Uninstalling .apk...')
      try:
        output = subprocess.check_output('adb uninstall %s' % class_path,
                                         shell=True)
        CheckAdbSuccess(output)
      except subprocess.CalledProcessError, e:
        logging.error('adb uninstall error %d:\n%s', e.returncode, e.output)
        sys.exit(e.returncode)
    
    logging.info('Monkey work done successfully.')
    return 0
  finally:
    logging.shutdown()


if __name__ == '__main__':
  main(sys.argv)
