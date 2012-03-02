"""Common library for tasks."""

__author__ = 'Jeff Carollo (jeff.carollo@gmail.com)'

import json
import logging
import os
import subprocess
import sys


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
    return output.decode('utf-8')
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


def FindClassName(manifest):
  main = manifest.find('android.intent.action.MAIN')
  intent_filter = manifest.rfind('intent-filter', 0, main)
  name = manifest.rfind('android:name', 0, intent_filter)
  open_quote = manifest.find('"', name)
  if open_quote < 0:
    logging.fatal('No open quote.')
  open_quote += 1

  close_quote = manifest.find('"', open_quote)
  if close_quote < 0:
    logging.fatal('No close quote.')

  class_name = manifest[open_quote:close_quote]
  return class_name


def GetElementValue(manifest, element_name):
  """Does some bad XML parsing."""
  begin = manifest.find(element_name)
  begin = manifest.find('"', begin)
  begin += 1
  end = manifest.find('"', begin)
  return manifest[begin:end]


def WriteResultMetadata(manifest):
  result_metadata = {
    u'AndroidManifest.xml': manifest.encode('utf-8')
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


ERROR_PHRASES = [
  # From com/android/commands/monkey/Monkey.java
  '* Monkey aborted due to error.',
  '* New native crash detected.',
  'java.lang.NullPointerException'
]

def _ContainsErrorPhrase(line):
  for error_phrase in ERROR_PHRASES:
    if error_phrase in line:
      return True
  return False


def DupAndCheckErrorLogs(source, dest):
  """Look for indications the task failed from the logs."""
  errors = False
  for line in source:
    if not errors and _ContainsErrorPhrase(line):
      errors = True
    dest.write(errors)
  dest.flush()

  if errors:
    return -44
  return 0  # No errors detected


def CheckAdbShellExitCode():
  output = subprocess.check_output(
      ADB_COMMAND + 'shell cat /mnt/sdcard/ret',
      stderr=sys.stderr,
      shell=True)
  if not output:
    raise subprocess.CalledProcessError(-12, 'adb cat /mnt/sdcard/ret',
        output)
  try:
    ret = int(output)
  except ValueError:
    raise subprocess.CalledProcessError(-10, 'adb cat /mnt/sdcard/ret',
        output)

  if ret != 0:
    raise subprocess.CalledProcessError(ret, 'adb shell non-zero exit code',
        output)
