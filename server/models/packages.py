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

"""Representation of a Package and related functionality."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

from google.appengine.ext import db
from google.appengine.ext.blobstore import blobstore

import datetime
import logging
import webapp2

from util import db_properties


class Error(Exception):
  pass


class DuplicatePackageError(Error):
  pass


class PackageFile(db.Model):
  """A reference to a file in blobstore along with manifest information.
  
  Could also be a reference to a file somewhere on the web, in which case
  there will be no blobstore info."""

  # Must set either blob or url, but not both or neither.
  blob = blobstore.BlobReferenceProperty(required=False)

  # Must include relative file path and file name of destination.
  destination = db.TextProperty(required=True)
  # Mode of file.  755 for an executable, for instance.
  file_mode = db.TextProperty(required=True)
  download_url = db.TextProperty(required=True)


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


def CreatePackage(name, version, created_by, files, urlfiles):
  if not name.isalpha():
    # TODO(jeff.carollo): Raise an appropriate Exception.
    logging.error('Must have alphabetic package name.')
    return None

  package_key = MakePackageKey(name, version)

  def tx():
    package = db.get(package_key)
    if package is not None:
      raise DuplicatePackageError()

    package = Package(key=package_key,
                      name=name,
                      version=version,
                      created_by=created_by)
    # TODO(jeff.carollo): Handle conflicting package name/version.
    db.put(package)

    package_files = []
    # Create PackageFiles with blob refs.
    for (blob_info, destination, file_mode, download_url) in files:
      # TODO(jeff.carollo): Create PackageFile.key from destination.
      package_files.append(PackageFile(parent=package_key,
                                       destination=destination,
                                       file_mode=file_mode,
                                       download_url=download_url,
                                       blob=blob_info))
    # Create PackageFiles with urls instead of blobrefs.
    for urlfile in urlfiles:
      package_files.append(PackageFile(parent=package_key,
                                       destination=urlfile['file_destination'],
                                       file_mode=urlfile['file_mode'],
                                       download_url=urlfile['url']))

    db.put(package_files)
    return package
  return db.run_in_transaction(tx)


def GetPackageByNameAndVersion(name, version):
  return db.get(MakePackageKey(name, version))


def GetPackageFilesByPackageNameAndVersion(name, version):
  package_key = MakePackageKey(name, version)
  # Beyond 10 files or so, people would be better off tar'ing stuff up.
  return PackageFile.all().ancestor(package_key).fetch(limit=1000) or []


def DeletePackageByNameAndVersion(name, version):
  def tx():
    package_key = MakePackageKey(name, version)
    package_keys = [package_key]
    package_keys.extend(
        PackageFile.all(keys_only=True)
                   .ancestor(package_key)
                   .fetch(limit=1000))
    db.delete(package_keys)
  return db.run_in_transaction(tx)
