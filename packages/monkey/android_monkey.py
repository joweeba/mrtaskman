#!/usr/bin/python

"""Executes Android Monkey stress test over adb to attached Android device."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

import json
import logging
import os
import subprocess
import sys
import time


def GetDeviceSerialNumber():
  """Returns the serial number of the device assigned to the current worker.

  Pulls from environment variables.

  Returns:
    Serial number as str, or None.
  """
  return os.environ.get('DEVICE_SN', None)


# Set ADB_COMMAND.
DEVICE_SN = GetDeviceSerialNumber()
if not DEVICE_SN:
  ADB_COMMAND = 'adb '
else:
  ADB_COMMAND = 'adb -s %s ' % DEVICE_SN


def RunShellCommand(command):
  try:
    subprocess.check_call(command,
                          stdout=sys.stdout,
                          stderr=sys.stderr,
                          shell=True)
  except subprocess.CalledProcessError, e:
    logging.error('Error %d:\n%s', e.returncode, e.output)
    sys.exit(e.returncode)


def ReadAndroidManifest(apk_file_path):
  APK_UNPACKED_DIR = '__apk_unpacked__'
  RunShellCommand('unzip %s -d %s' % (apk_file_path, APK_UNPACKED_DIR))
  android_manifest_path = os.path.join(APK_UNPACKED_DIR, 'AndroidManifest.xml')

  try:
    output = subprocess.check_output(
        'java -jar AXMLPrinter2.jar %s' % android_manifest_path,
        shell=True)
    return output
  except subprocess.CalledProcessError, e:
    logging.error('AXMLPrinter2 error %d:\n%s', e.returncode, e.output)
    sys.exit(e.returncode)


def FindClassPath(manifest):
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


def GetElementValue(manifest, element_name):
  """Does some bad XML parsing."""
  begin = manifest.find(element_name)
  begin = manifest.find('"', begin)
  begin += 1
  end = manifest.find('"', begin)
  return manifest[begin:end]


def WriteResultMetadata(manifest):
  '''
  version_code = GetElementValue(manifest, 'android:versionCode')
  version_name = GetElementValue(manifest, 'android:versionName')
  package = GetElementValue(manifest, 'package')
  result_metadata = {
      'version_code': version_code,
      'version_name': version_name,
      'package': package
  }
  '''
  result_metadata = {
    'AndroidManifest.xml': manifest
  }
  outfile = file('result_metadata', 'w')
  json.dump(result_metadata, outfile)
  outfile.close()


def CheckAdbSuccess(adb_output):
  """Cover the fail."""
  if 'Success' in adb_output:
    return
  adb_output.returncode = -5
  raise subprocess.CalledProcessError(-1, 'adb', output=adb_output)


MONKEY_COMMAND = ADB_COMMAND + 'shell /system/bin/monkey -p %s --kill-process-after-error -v 5000 --pct-touch 10 --pct-trackball 90 -s 10 %s'


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
    manifest = ReadAndroidManifest(apk_file_path)
    class_path = FindClassPath(manifest)
    WriteResultMetadata(manifest)
    logging.info('Found class_path: %s', class_path)

    logging.info('Installing .apk...')
    try:
      output = subprocess.check_output(
          ADB_COMMAND + 'install -r %s' % apk_file_path,
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
        output = subprocess.check_output(
            ADB_COMMAND + 'uninstall %s' % class_path,
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
