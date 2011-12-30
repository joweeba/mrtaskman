"""Representation of a Package and related functionality."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

from google.appengine.ext import db
from google.appengine.ext.blobstore import blobstore

import datetime
import logging
import webapp2

from util import db_properties


class PackageFile(db.Model):
  """A reference to a file in blobstore along with manifest information."""
  blob = blobstore.BlobReferenceProperty(required=True)
  # Must include relative file path and file name of destination.
  destination = db.TextProperty(required=True)
  # Mode of file.  755 for an executable, for instance.
  file_mode = db.TextProperty(required=True)


class Package(db.Model):
  """MrTaskman's representation of a Package.
  
  A Package will have a number of associated PackageFiles, all sharing the
  same unique parent key as the Package itself."""
  name = db.StringProperty(required=True)
  version = db.StringProperty(required=True)
  created = db.DateTimeProperty(auto_now_add=True)
  modified = db.DateTimeProperty(auto_now_add=True)
  created_by = db.UserProperty(required=False)


def MakePackageKey(name, version):
  return db.Key.from_path('Package', '%s^^^%s' % (name, version))


def CreatePackage(name, version, created_by, files):
  if not name.isalpha():
    # TODO(jeff.carollo): Raise an appropriate Exception.
    logging.error('Must have alphabetic package name.')
    return None

  package_key = MakePackageKey(name, version)

  def tx():
    package = Package(key=package_key,
                      name=name,
                      version=version,
                      created_by=created_by)
    # TODO(jeff.carollo): Handle conflicting package name/version.
    db.put(package)

    package_files = []
    for (blob_info, destination, file_mode) in files:
      # TODO(jeff.carollo): Create PackageFile.key from destination.
      package_files.append(PackageFile(parent=package_key,
                                       destination=destination,
                                       file_mode=file_mode,
                                       blob=blob_info))
    db.put(package_files)
    return package
  return db.run_in_transaction(tx)


def GetPackage(name, version):
  return db.get(MakePackageKey(name, version))

def GetPackageFiles(name, version):
  package_key = MakePackageKey(name, version)
  # Beyond 10 files or so, people would be better off tar'ing stuff up.
  return PackageFile.all(parent=package_key).fetch(limit=1000)
