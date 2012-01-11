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

"""MrTaskman client command-line utility.

Allows users to upload configs, check the results of tasks, etc.
"""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

import gflags
import json
import logging
import sys
import urllib2

from client import mrtaskman_api


FLAGS = gflags.FLAGS


def Help(unused_argv):
  print Usage()
  return 0


def Task(argv):
  try:
    task_id = int(argv.pop(0))
  except:
    sys.stderr.write('task command requires an integer task_id argument.\n')
    return 3

  api = mrtaskman_api.MrTaskmanApi()

  try:
    task = api.GetTask(task_id)
    json.dump(task, sys.stdout, indent=2)
    print ''
    return 0
  except urllib2.HTTPError, e:
    sys.stderr.write('Got %d HTTP response from MrTaskman:\n%s\n' % (
                          e.code, e.read()))
    return e.code


def Schedule(argv):
  try:
    config_filepath = argv.pop(0)
  except:
    sys.stderr.write('schedule command requires a config filepath argument.\n')
    return 3

  try:
    config_file = file(config_filepath, 'r')
  except Exception, e:
    sys.stderr.write('Error opening %s:\n%s\n' % (config_filepath, e))
    return 4

  try:
    config = json.load(config_file)
  except Exception, e:
    sys.stderr.write('Error reading or parsing config file:\n%s\n' % e)
    return 5

  api = mrtaskman_api.MrTaskmanApi()

  try:
    task_result = api.ScheduleTask(config)
    json.dump(task_result, sys.stdout, indent=2)
    print ''
    return 0
  except urllib2.HTTPError, e:
    sys.stderr.write('Got %d HTTP response from MrTaskman:\n%s\n' % (
                          e.code, e.read()))
    return e.code


def DeleteTask(argv):
  try:
    task_id = int(argv.pop(0))
  except:
    sys.stderr.write(
        'deletetask command requires an integer task_id argument.\n')
    return 3

  api = mrtaskman_api.MrTaskmanApi()

  try:
    api.DeleteTask(task_id)
    print 'Successfully deleted task %d' % task_id
    return 0
  except urllib2.HTTPError, e:
    sys.stderr.write('Got %d HTTP response from MrTaskman:\n%s\n' % (
                          e.code, e.read()))
    return e.code


def CreatePackage(argv):
  try:
    package_filepath = argv.pop(0)
  except:
    sys.stderr.write(
        'createpackage command requires a package filepath argument.\n')
    return 3

  try:
    package_file = file(package_filepath, 'r')
  except Exception, e:
    sys.stderr.write('Error opening %s:\n%s\n' % (package_filepath, e))
    return 4

  try:
    package = json.load(package_file)
  except Exception, e:
    sys.stderr.write('Error reading or parsing package file:\n%s\n' % e)
    return 5

  api = mrtaskman_api.MrTaskmanApi()

  try:
    package_result = api.CreatePackage(package)
    json.dump(package_result, sys.stdout, indent=2)
    print ''
    return 0
  except urllib2.HTTPError, e:
    sys.stderr.write('Got %d HTTP response from MrTaskman:\n%s\n' % (
                          e.code, e.read()))
    return e.code


def DeletePackage(argv):
  try:
    package_name = argv.pop(0)
  except:
    sys.stderr.write(
        'deletepackage command requires a string package name argument.\n')
    return 3
  try:
    package_id = int(argv.pop(0))
  except:
    sys.stderr.write(
        'deletepackage command requires an int package id argument.\n')
    return 3

  api = mrtaskman_api.MrTaskmanApi()

  try:
    api.DeletePackage(package_name, package_id)
    print 'Successfully deleted package %s.%d' % (package_name, package_id)
    return 0
  except urllib2.HTTPError, e:
    sys.stderr.write('Got %d HTTP response from MrTaskman:\n%s\n' % (
                          e.code, e.read()))
    return e.code


def Package(argv):
  try:
    package_name = argv.pop(0)
  except:
    sys.stderr.write(
        'package command requires a string package name argument.\n')
    return 3
  try:
    package_id = int(argv.pop(0))
  except:
    sys.stderr.write(
        'package command requires an int package id argument.\n')
    return 3

  api = mrtaskman_api.MrTaskmanApi()

  try:
    package = api.GetPackage(package_name, package_id)
    json.dump(package, sys.stdout, indent=2)
    print ''
    return 0
  except urllib2.HTTPError, e:
    sys.stderr.write('Got %d HTTP response from MrTaskman:\n%s\n' % (
                          e.code, e.read()))
    return e.code


def Usage():
  return (
"""mrt.py - MrTaskman client command-line utility.

USAGE:
  mrt.py [options] command [args]

COMMANDS:
  help\t\t\tPrints this message.

  deletetask {id}\tDelete task with given id.
  schedule {task_file}\tSchedules a new task from given task_file.
  task {id}\t\tRetrieve information on given task id.
  tasks\t\t\tList available tasks.

  createpackage {manifest}\t Create a new package with given manifest.
  deletepackage {name} {version} Delete package with given name and version.
  package {name} {version}\t Retrieve information on given package.
  packages\t\t\t List existing packages.""")


# Mapping of command text to command function.
COMMANDS = {
  'help': Help,
  'deletetask': DeleteTask,
  'schedule': Schedule,
  'task': Task,
  'createpackage': CreatePackage,
  'deletepackage': DeletePackage,
  'package': Package,
}


def main(argv):
  # Parse command-line flags.
  try:
    argv = FLAGS(argv)
  except gflags.FlagsError, e:
    sys.stderr.write(Usage())
    sys.stderr.write('%s\n' % e)
    sys.exit(1)

  # Set up logging.
  FORMAT = '%(asctime)-15s %(message)s'
  logging.basicConfig(format=FORMAT, level=logging.INFO)

  try:
    mrt = argv.pop(0)

    # Parse command.
    try:
      command = argv.pop(0)
      logging.debug('command: %s', command)
    except:
      return Help([])

    # Invoke command.
    try:
      return COMMANDS[command](argv)
    except KeyError:
      sys.stderr.write('Command %s not found.\nSee mrt.py help.' % command)
      return 2
  finally:
    # Nothing should be done after the next line.
    logging.shutdown()


if __name__ == '__main__':
  main(sys.argv)
