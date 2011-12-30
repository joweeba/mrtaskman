"""TaskResult file download handler.

This module uses blobstore_handlers, which is webapp1 stuff.
No available AppEngine documentation talks about having a webapp2
equivalent for doing blobstore_handlers.BlobstoreDownloadHandler.send_blob.
This should all be converted to webapp2 when send_blob becomes available.
"""

__author__ = 'jeff.carollo@gmail.com (Jeff Carollo)'

from google.appengine.ext import blobstore
from google.appengine.ext import webapp
from google.appengine.ext.webapp import blobstore_handlers
from google.appengine.ext.webapp.util import run_wsgi_app


class TaskResultFileDownloadHandler(
    blobstore_handlers.BlobstoreDownloadHandler):
  def get(self, file_key):
    if not blobstore.get(file_key):
      self.error(404)
    else:
      self.send_blob(file_key)


application = webapp.WSGIApplication([
    ('/taskresultfiles/(.+)', TaskResultFileDownloadHandler),
    ], debug=True)


def main():
  run_wsgi_app(application)


if __name__ == '__main__':
  main()
