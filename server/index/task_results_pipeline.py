# Copyright 2012 uTest, Inc. All Rights Reserved.

"""Migrates Tasks from old key scheme to new one."""

__author__ = 'Jeff Carollo (jeffc@utest.com)'

import logging

from mapreduce import base_handler
from mapreduce import mapreduce_pipeline
from mapreduce import operation

from models import tasks


class TaskResultsPipeline(base_handler.PipelineBase):
  def run(self):
    yield mapreduce_pipeline.MapperPipeline(
        'TaskResultsPipeline',
        'index.task_results_pipeline.Map',
        'mapreduce.input_readers.DatastoreInputReader',
        params={
          'entity_kind': 'models.tasks.TaskResult',
          'batch_size': 100,
        },
        shards=100)


def Map(task_result):
  if task_result.device_serial_number is None:
    yield operation.counters.Increment('no_device_sn')
    return
  yield operation.counters.Increment(task_result.device_serial_number)
  if task_result.exit_code == 0:
    yield operation.counters.Increment(
        task_result.device_serial_number + '_successes')
  else:
    yield operation.counters.Increment(
        task_result.device_serial_number + '_failures')
  yield operation.counters.Increment('exit_code_%s' % task_result.exit_code)
