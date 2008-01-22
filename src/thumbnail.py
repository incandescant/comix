# ============================================================================
# thumbnail.py - Thumbnail module for Comix implementing (most of) the
# freedesktop.org "standard" at http://jens.triq.net/thumbnail-spec/
#
# Only normal size (i.e. 128x128 px) thumbnails are supported.
# ============================================================================

import os
from urllib import pathname2url, url2pathname
import md5
import re
import shutil
import tempfile

import gtk
import Image

import archive
import constants
import filehandler

_thumbdir = os.path.join(os.getenv('HOME'), '.thumbnails/normal')

def get_thumbnail(path, create=True):
    
    """
    Get a thumbnail pixbuf for the file at <path> by looking in the
    directory of stored thumbnails. If a thumbnail for the file doesn't
    exist we create a thumbnail pixbuf from the original. If <create>
    is True we also save this new thumbnail in the thumbnail directory.
    If no thumbnail for <path> can be produced (for whatever reason), 
    return None.

    Images and archives are handled transparently. Note though that
    None is always returned for archives where no thumbnail already exist
    if <create> is False, since re-creating the thumbnail on the fly each
    time would be too costly.
    """
    
    thumbpath = _path_to_thumbpath(path)
    if not os.path.exists(thumbpath):
        return _get_new_thumbnail(path, create)
    try:
        info = Image.open(thumbpath).info
        if (not info.has_key('Thumb::MTime') or 
          os.stat(path).st_mtime != int(info['Thumb::MTime'])):
            return _get_new_thumbnail(path, create)
        return gtk.gdk.pixbuf_new_from_file(thumbpath)
    except:
        return None

def _get_new_thumbnail(path, create):
    
    """
    Return a new thumbnail pixbuf for the file at <path>. If <create> is
    True we also save it to disk.
    """
    
    if archive.archive_mime_type(path):
        if create:
            return _get_new_archive_thumbnail(path)
        return None
    if create:
        return _create_thumbnail(path)
    return _get_pixbuf128(path)
        
def _get_new_archive_thumbnail(path):
    
    """
    Return a new thumbnail pixbuf for the archive at <path>, and save it
    to disk.
    """
    
    extractor = archive.Extractor()
    tmpdir = tempfile.mkdtemp(prefix='comix_archive_thumb.')
    condition = extractor.setup(path, tmpdir)
    files = extractor.get_files()
    wanted = _guess_cover(files)
    if wanted == None:
        return None
    extractor.set_files([wanted])
    extractor.extract()
    image_path = os.path.join(tmpdir, wanted)
    condition.acquire()
    while not extractor.is_ready(wanted):
        condition.wait()
    condition.release()
    pixbuf = _create_thumbnail(path, image_path)
    shutil.rmtree(tmpdir)
    return pixbuf

def _create_thumbnail(path, image_path=None):
    
    """
    Create a thumbnail from the file at <path> and store it in the standard
    thumbnail directory, if it is larger than 128x128 px. A pixbuf for the
    thumbnail is returned.

    If <image_path> is not None it is used as the path to the image file
    actually used to create the thumbnail image, although the created 
    thumbnail will still be saved as if for <path>.
    """
    
    if image_path == None:
        image_path = path
    pixbuf = _get_pixbuf128(image_path)
    if pixbuf == None:
        return None
    mime, width, height = gtk.gdk.pixbuf_get_file_info(image_path)
    if width <= 128 and height <= 128:
        return pixbuf
    mime = mime['mime_types'][0]
    uri = 'file://' + pathname2url(os.path.normpath(path))
    thumbpath = _uri_to_thumbpath(uri)
    stat = os.stat(path)
    mtime = str(stat.st_mtime)
    size = str(stat.st_size)
    width = str(width)
    height = str(height)
    tEXt_data = {
        'tEXt::Thumb::URI':           uri,
        'tEXt::Thumb::MTime':         mtime,
        'tEXt::Thumb::Size':          size,
        'tEXt::Thumb::Mimetype':      mime,
        'tEXt::Thumb::Image::Width':  width,
        'tEXt::Thumb::Image::Height': height,
        'tEXt::Software':             'Comix ' + constants.VERSION
    }
    try:
        if not os.path.isdir(_thumbdir):
            os.makedirs(_thumbdir, 0700)
        pixbuf.save(thumbpath + 'comixtemp', 'png', tEXt_data)
        os.rename(thumbpath + 'comixtemp', thumbpath)
        os.chmod(thumbpath, 0600)
    except:
        print '! thumbnail.py: Could not write', thumbpath, '\n'
    return pixbuf

def _path_to_thumbpath(path):
    uri = 'file://' + pathname2url(os.path.normpath(path))
    return _uri_to_thumbpath(uri)

def _uri_to_thumbpath(uri):
    md5hash = md5.new(uri).hexdigest()
    thumbpath = os.path.join(_thumbdir, md5hash + '.png')
    return thumbpath

def _get_pixbuf128(path):
    try:
        return gtk.gdk.pixbuf_new_from_file_at_size(path, 128, 128)
    except:
        return None

def _guess_cover(files):
    
    """
    Return the filename within <files> that is the most likely to be the
    cover of an archive.
    """
    
    files.sort()
    ext_re = re.compile(r'\.(jpg|jpeg|png|gif|tif|tiff)\s*$', re.I)
    front_re = re.compile('((?<!back)cover)|(front)', re.I)
    images = filter(ext_re.search, files)
    candidates = filter(front_re.search, images)
    candidates = [c for c in candidates if not 'back' in c.lower()]
    if candidates:
        return candidates[0]
    if images:
        return images[0]
    return None

