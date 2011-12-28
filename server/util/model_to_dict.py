"""Converts AppEngine db.Model's to JSON."""

from google.appengine.ext import db

import datetime
import json
import time

from util import db_properties


SIMPLE_TYPES = (int, long, float, bool, dict, basestring, list)


def ModelToDict(model):
  """Returns dictionary from given db.Model."""
  assert isinstance(model, db.Model)
  output = {}
  output['id'] = model.key().id_or_name()

  for key, prop in model.properties().iteritems():
    value = getattr(model, key)

    if value is None:
      output[key] = value
    elif isinstance(prop, db_properties.JsonProperty):
      output[key] = json.loads(value)
    elif isinstance(value, SIMPLE_TYPES):
      output[key] = value
    elif isinstance(value, datetime.date):
      # Convert date/datetime to ms-since-epoch ("new Date()").
      ms = time.mktime(value.utctimetuple()) * 1000
      ms += getattr(value, 'microseconds', 0) / 1000
      output[key] = int(ms)
    elif isinstance(value, db.GeoPt):
      output[key] = {'lat': value.lat, 'lon': value.lon}
    elif isinstance(value, db.Model):
      output[key] = ModelToDict(value)
    else:
      raise ValueError('cannot encode ' + repr(prop))

  return output
