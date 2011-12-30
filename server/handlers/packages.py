"""Handlers for the MrTaskman Tasks API."""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

from google.appengine.api import users
from google.appengine.ext.blobstore import blobstore

import cgi
import copy
import json
import logging
import urllib
import webapp2

from models import packages
from util import model_to_dict


class PackagesError(Exception):
  def __init__(self, message):
    Exception.__init__(self, message)


class InvalidManifestJsonError(PackagesError):
  pass


class MissingFileFromFormError(PackagesError):
  pass
  

class PackagesCreateHandler(webapp2.RequestHandler):
  """Handles the creation of a new Task, also known as scheduling."""

  def get(self):
    """Convenience HTML form for testing."""
    # TODO(jeff.carollo): Have someone make this a dynamic form
    # with Javascript.  Possibly have it generate manifest.

    upload_url = blobstore.create_upload_url('/packages/create')
    self.response.out.write(
        """
        <html><head><title>Package Creator</title></head><body>
        <form id="package" action="%s"
              method="POST" enctype="multipart/form-data">
          Upload File1: <input type="file" name="file1"/><br/>
          Upload File2: <input type="file" name="file2"/><br/>
          Manifest: <input type="textarea" name="manifest" rows="40" cols="80"/><br/> 
          <input type="submit" name="submit" value="Submit"/>
        </form>
        </body></html>
        """ % upload_url)

  def post(self):
    """Called following blobstore writes with blob_keys replacing file data."""

    logging.info('Request: %s', self.request.body)

    blob_infos = self.GetBlobInfosFromPostBody()

    manifest = self.request.get('manifest', None)
    if manifest:
      manifest = urllib.unquote(manifest.decode('utf-8'))
    if manifest:
      try:
        manifest = json.loads(manifest, 'utf-8')
      except ValueError, e:
        self.response.out.write('Field "manifest" must be valid JSON.')
        logging.info(e)
        manifest = None
    if not manifest:
      self.DeleteAllBlobs(blob_infos)
      self.response.out.write('Field "manifest" is required.')
      self.response.set_status(400)
      return

    try:
      files = self.MakeFilesListFromManifestAndBlobs(manifest, blob_infos)
    except PackagesError, e:
      self.DeleteAllBlobs(blob_infos)
      self.response.out.write(e.message())
      self.response.set_status(400)
      return

    try:
      package_name = manifest['name']
      package_version = manifest['version']
    except KeyError:
      self.DeleteAllBlobs(blob_infos)
      self.response.out.write('Package "name" and "version" are required.')
      self.response.set_status(400)
      return
      
    package = packages.CreatePackage(package_name, package_version,
                                     users.get_current_user(), files)

    if not package:
      self.response.out.write('Unable to create package (unknown reason).')
      self.DeleteAllBlobs(blob_infos)
      self.response.set_status(500)

    response = model_to_dict.ModelToDict(package)
    response['kind'] = 'mrtaskman#create_package_response'
    json.dump(response, self.response.out, indent=2)
    self.response.out.write('\n')

  def GetBlobInfosFromPostBody(self):
    """Returns a dict of {'form_name': blobstore.BlobInfo}."""
    blobs = {}
    for (field_name, field_storage) in self.request.POST.items():
      if isinstance(field_storage, cgi.FieldStorage):
        blobs[field_name] = blobstore.parse_blob_info(field_storage)
    return blobs

  def DeleteAllBlobs(self, blob_infos):
    """Deletes all blobs referenced in this request.

    Should be called whenever post() returns a non-200 response.
    """
    for (_, blob_info) in blob_infos.items():
      blob_info.delete()

  def MakeFilesListFromManifestAndBlobs(self, manifest, blob_infos):
    """Returns a list of (blob_info, destination, file_mode) from inputs."""
    files = []
    for form_file in manifest['files']:
      try:
        form_name = form_file['form_name']
      except KeyError:
        raise InvalidManifestJsonError('Missing required form_name in file.')

      try:
        destination = form_file['file_destination']
      except KeyError:
        raise InvalidManifestJsonError(
            'Missing required file_destination in file.')

      try:
        file_mode = form_file['file_mode']
      except KeyError:
        raise InvalidManifestJsonError('Missing required file_mode in file.')

      try:
        blob_info = blob_infos[form_name]
      except KeyError:
        raise MissingFileFromFormError('Missing form value for %s' % form_name)

      files.append((blob_info, destination, file_mode))
    return files


app = webapp2.WSGIApplication([
    ('/packages/create', PackagesCreateHandler),
    ], debug=True)
