# Copyright 2012 uTest, Inc. All Rights Reserved.

"""Migrates Tasks from old key scheme to new one."""

__author__ = 'Jeff Carollo (jeffc@utest.com)'

import logging

from mapreduce import base_handler
from mapreduce import mapreduce_pipeline
from mapreduce import operation

from models import tasks


class MigrateTasksPipeline(base_handler.PipelineBase):
  def run(self):
    yield mapreduce_pipeline.MapperPipeline(
        'MigrateTasks',
        'index.migrate_tasks_pipeline.Map',
        'mapreduce.input_readers.DatastoreInputReader',
        params={
          'entity_kind': 'models.tasks.Task',
          'batch_size': 100,
        },
        shards=100)


def Map(model):
  if model.parent() is not None:
    model_dict = db.to_dict(model)
    model2 = tasks.Task(key=db.Key.from_path('Task', model.key().id()),
                        **model_dict)
    operation.db.Put(model2)
