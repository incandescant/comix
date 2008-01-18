# ============================================================================
# filehandler.py - File handler for Comix. Opens files and keeps track
# of images, pages and caches.
#
# Other modules should *never* read directly from the files pointed to by
# paths given by the FileHandler's methods. The files are not even
# guaranteed to exist at all times.
# ============================================================================

import os
import sys
import shutil
import locale
import tempfile
import gc
import shutil
import threading
import time
import re

import gtk

import archive
import cursor
import encoding
import image
from preferences import prefs
import thumbnail

class FileHandler:

    def __init__(self, window):
        self.file_loaded = False
        self.archive_type = None
        
        self._base_path = None
        self._window = window
        self._tmp_dir = tempfile.mkdtemp(prefix='comix.')
        self._image_files = []
        self._current_image_index = None
        self._comment_files = []
        self._raw_pixbufs = {}
        self._extractor = archive.Extractor()
        self._condition = None
        self._image_re = re.compile(r'\.(jpg|jpeg|png|gif|tif|tiff)\s*$', re.I)
        #self._comment_re = re.compile(r'\.(%s)'%  , re.I)

    def _get_pixbuf(self, index):
        
        """
        Returns the pixbuf for <page> from cache.
        Pixbufs not found in cache are fetched from disk first. 
        """

        if not self._raw_pixbufs.has_key(index):
            self._wait_on_page(index + 1)
            try:
                self._raw_pixbufs[index] = gtk.gdk.pixbuf_new_from_file(
                    self._image_files[index])
            except:
                self._raw_pixbufs[index] = self._get_missing_image()
        return self._raw_pixbufs[index]

    def get_pixbufs(self, single=False):

        """
        Returns the pixbuf(s) for the current image(s) from cache.
        Returns two pixbufs in double-page mode unless <single> is True.
        Pixbufs not found in cache are fetched from disk first. 
        """

        if not self._window.displayed_double() or single:
            return self._get_pixbuf(self._current_image_index)
        return (self._get_pixbuf(self._current_image_index),
                self._get_pixbuf(self._current_image_index + 1))

    def do_cacheing(self):

        """
        Makes sure that the correct pixbufs are stored in cache. These
        are the current image(s) and if cacheing is enabled also the one or two
        pixbufs before and after them. All other pixbufs are deleted and
        garbage collected in order to save memory.
        """
        
        # Get list of wanted pixbufs.
        viewed = self._window.is_double_page and 2 or 1
        if prefs['cache']:
            wanted_pixbufs = range(max(0, self._current_image_index - viewed), 
                min(self._current_image_index + viewed * 2,
                    self.get_number_of_pages()))
        else:
            wanted_pixbufs = range(self._current_image_index, 
                min(self._current_image_index + viewed,
                    self.get_number_of_pages()))
        
        # Remove old pixbufs.
        for page in self._raw_pixbufs.keys()[:]:
            if not page in wanted_pixbufs:
                del self._raw_pixbufs[page]
        if sys.version_info[:3] >= (2, 5, 0):
            gc.collect(0)  # FIXME: Try this (i.e. get Python 2.5)!
        else:
            gc.collect()

        # Cache new pixbufs if not already cached.
        for wanted in wanted_pixbufs:
            self._get_pixbuf(wanted)

    def next_page(self):

        """
        Sets up filehandler to the next page. Returns True if this is not
        the same page, False otherwise.
        """

        if not self.file_loaded:
            return False
        old_image = self.get_current_page()
        step = self._window.is_double_page and 2 or 1
        if self.get_current_page() + step > self.get_number_of_pages():
            if prefs['auto open next archive'] and self.archive_type:
                self._open_next_archive()
            return False
        self._current_image_index += step
        self._current_image_index = min(self.get_number_of_pages() - 1,
            self._current_image_index)
        return old_image != self.get_current_page()

    def previous_page(self):

        """
        Sets up filehandler to the previous page. Returns True if this is not
        the same page, False otherwise.
        """

        if not self.file_loaded:
            return False
        if self.get_current_page() == 1:
            if prefs['auto open next archive'] and self.archive_type:
                self._open_previous_archive()
            return False
        old_image = self.get_current_page()
        step = self._window.is_double_page and 2 or 1
        self._current_image_index -= step
        self._current_image_index = max(0, self._current_image_index)
        return old_image != self.get_current_page()

    def first_page(self):

        """
        Sets up filehandler to the first page. Returns True if this is not
        the same page, False otherwise.
        """

        if not self.file_loaded:
            return False
        old_image = self.get_current_page()
        self._current_image_index = 0
        return old_image != self.get_current_page()

    def last_page(self):

        """ 
        Sets up filehandler to the last page. Returns True if this is not
        the same page, False otherwise.
        """
        
        if not self.file_loaded:
            return False
        old_image = self.get_current_page()
        offset = self._window.is_double_page and 2 or 1
        self._current_image_index = max(0, self.get_number_of_pages() - offset)
        return old_image != self.get_current_page()

    def set_page(self, page_num):

        """ 
        Sets up filehandler to the page <page_num>. Returns True if this is
        not the same page, False otherwise.
        """

        old_image = self.get_current_page()
        if not 0 < page_num <= self.get_number_of_pages():
            return False
        self._current_image_index = page_num - 1
        return old_image != self.get_current_page()

    def open_file(self, path, start_page=1):

        """
        If <path> is an image we add all images in its directory to the
        _image_files.

        If <path> is an archive we decompresses it to the _tmp_dir and adds
        all images in the decompressed tree to _image_files and all comments
        to _comment_files. If <start_image> is not set we set current page
        to 1 (first page), if it is set we set it to the value of
        <start_page>. If <start_page> is non-positive it means the last image.
        """
        
        # --------------------------------------------------------------------
        # If the given <path> is invalid we update the statusbar.
        # --------------------------------------------------------------------
        if not os.path.isfile(path):
            if os.path.isdir(path):
                self._window.statusbar.set_message(_('"%s" is not a file.') % 
                    os.path.basename(path))
            else:
                self._window.statusbar.set_message(_('"%s" does not exist.') % 
                    os.path.basename(path))
            return False

        self.archive_type = archive.archive_mime_type(path)
            
        if not self.archive_type and not is_image_file(path):
            self._window.statusbar.set_message(
                _('Filetype of "%s" not recognized.') % os.path.basename(path))
            return False

        cursor.set_cursor_type(cursor.WAIT)
        if self.file_loaded:
            self.close_file()
        while gtk.events_pending():
            gtk.main_iteration(False)

        # --------------------------------------------------------------------
        # If <path> is an archive we extract it and walk down the extracted
        # tree to find images and comments.
        # --------------------------------------------------------------------
        if self.archive_type:
            self._base_path = path
            #t = time.time()
            self._condition = self._extractor.setup(path, self._tmp_dir)
            #print 'create extractor:', time.time() - t
            #t = time.time()
            files = self._extractor.get_files()
            #print files
            image_files = filter(self._image_re.search, files)
            image_files.sort()
            self._image_files = \
                [os.path.join(self._tmp_dir, f) for f in image_files]
            self._extractor.set_files(image_files)
            #print 'sort:', time.time() - t
            #t = time.time()
            self._extractor.extract()
            #print 'extract:', time.time() - t
            #t = time.time()

            #archive.extract_archive(path, self._tmp_dir)
            #for dirname, dirs, files in os.walk(self._tmp_dir):
            #    for f in files:
            #        fpath = os.path.join(dirname, f)
            #        if is_image_file(fpath):
            #            self._image_files.append(fpath)
            #        elif (os.path.splitext(f)[1].lower() in
            #          prefs['comment extensions']):
            #            self._comment_files.append(fpath)
                    #elif archive.archive_mime_type(fpath):
                    #    subdir = tempfile.mkdtemp(dir=dirname, prefix=f)
                    #    archive.extract_archive(fpath, subdir)
                    #    dirs.append(subdir)
            #self._image_files.sort()  # We don't sort archives after locale
            if start_page <= 0:
                if self._window.is_double_page:
                    self._current_image_index = self.get_number_of_pages() - 2
                else:
                    self._current_image_index = self.get_number_of_pages() - 1
            else:
                self._current_image_index = start_page - 1
            self._current_image_index = max(0, self._current_image_index)
            #print 'other:', time.time() - t

        # --------------------------------------------------------------------
        # If <path> is an image we scan it's directory for more images and
        # comments.
        # --------------------------------------------------------------------
        else:
            self._base_path = os.path.dirname(path)
            for f in os.listdir(os.path.dirname(path)):
                fpath = os.path.join(os.path.dirname(path), f)
                if is_image_file(fpath):
                    self._image_files.append(fpath)
            self._image_files.sort(locale.strcoll)
            self._current_image_index = self._image_files.index(path)

        # --------------------------------------------------------------------
        # If there are no viewable image files found.
        # --------------------------------------------------------------------
        if not self._image_files:
            self._window.statusbar.set_message(_('No images in "%s"') % 
                os.path.basename(path))
            self.file_loaded = False
        else:
            self.file_loaded = True
        
        self._comment_files.sort()
        self._window.thumbnailsidebar.block()
        self._window.new_page()
        cursor.set_cursor_type(cursor.NORMAL)
        while gtk.events_pending():
            gtk.main_iteration(False)
        self._window.ui_manager.set_sensitivities()
        self._window.thumbnailsidebar.unblock()
        self._window.thumbnailsidebar.load_thumbnails()
        self._window.ui_manager.recent.add(path)

    def close_file(self, *args):
        
        """ Runs tasks for "closing" the currently opened file(s) """

        self.file_loaded = False
        self._base_path = None
        self._image_files = []
        self._current_image_index = None
        self._comment_files = []
        self._raw_pixbufs.clear()
        self._window.clear()
        self._window.ui_manager.set_sensitivities()
        self._extractor.stop()
        thread_delete(self._tmp_dir)
        self._tmp_dir = tempfile.mkdtemp(prefix='comix.')
        gc.collect()

    def cleanup(self):
        
        """ Runs clean-up tasks. Should be called prior to exit """

        self._extractor.stop()
        thread_delete(self._tmp_dir)

    def _open_next_archive(self):

        """
        Opens the archive that comes directly after the currently loaded
        archive in that archive's directory listing, sorted alphabetically.
        """

        arch_dir = os.path.dirname(self._base_path)
        files = os.listdir(arch_dir)
        files.sort(locale.strcoll)
        current_index = files.index(os.path.basename(self._base_path))
        for f in files[current_index + 1:]:
            path = os.path.join(arch_dir, f)
            if archive.archive_mime_type(path):
                self.open_file(path)
                return

    def _open_previous_archive(self):
        
        """
        Opens the archive that comes directly before the currently loaded
        archive in that archive's directory listing, sorted alphabetically.
        """

        arch_dir = os.path.dirname(self._base_path)
        files = os.listdir(arch_dir)
        files.sort(locale.strcoll)
        current_index = files.index(os.path.basename(self._base_path))
        for f in reversed(files[:current_index]):
            path = os.path.join(arch_dir, f)
            if archive.archive_mime_type(path):
                self.open_file(path, 0)
                return

    def _get_missing_image(self):
        
        """ Returns a pixbuf depicting a missing/broken image. """

        return self._window.render_icon(gtk.STOCK_MISSING_IMAGE,
            gtk.ICON_SIZE_DIALOG)

    def is_last_page(self):
        
        """ Returns True if at the last page. """
        
        if self._window.displayed_double():
            return self.get_current_page() + 1 >= self.get_number_of_pages()
        else:
            return self.get_current_page() == self.get_number_of_pages()

    def get_number_of_pages(self):
        
        """ Returns the number of pages in the current archive/directory. """

        return len(self._image_files)

    def get_current_page(self):
        
        """ Returns the current page number. """

        return self._current_image_index + 1

    def get_number_of_comments(self):
        
        """
        Returns the number of comments in the current archive/directory.
        """

        return len(self._comment_files)

    def get_comment_text(self, num):
        
        """ 
        Returns the text in comment <num> or None if comment <num> is not
        readable.
        """
        
        self._wait_on_comment(num)
        try:
            fd = open(self._comment_files[num - 1])
            text = fd.read()
            fd.close()
        except:
            text = None
        return text

    def get_comment_name(self, num):
        
        """ Returns the filename of comment <num>. """

        return self._comment_files[num]

    def get_pretty_current_filename(self):
        
        """
        Returns a string with the name of the currently viewed file that is
        suitable for printing.
        """

        if self.archive_type:
            return os.path.basename(self._base_path)
        return os.path.join(os.path.basename(self._base_path),
            os.path.basename(self._image_files[self._current_image_index]))

    def get_path_to_page(self, page=None):
        
        """
        Returns the full path to the image file for <page>, or the current
        page if <page> is None.
        """

        if page == None:
            return self._image_files[self._current_image_index]
        return self._image_files[page - 1]

    def get_path_to_base(self):
        
        """
        Returns the full path to the current base (path to archive or
        image directory.)
        """

        return self._base_path

    def get_real_path(self):
        
        """
        Returns the "real" path to the currenlty viewed file, i.e. the
        full path to the archive or the full path to the currently
        viewed image.
        """

        if self.archive_type:
            return self.get_path_to_base()
        return self._image_files[self._current_image_index]

    def get_size(self, page=None):
        
        """
        Returns a tuple (width, height) with the size of <page>. If <page>
        is None, returns the size of the current page.
        """

        self._wait_on_page(page)
        info = gtk.gdk.pixbuf_get_file_info(self.get_path_to_page(page))
        if info != None:
            return (info[1], info[2])
        return (0, 0)

    def get_mime_name(self, page=None):

        """
        Returns a string with the name of the mime type of <page>. If
        <page> is None, returns the mime type name of the current page.
        """

        self._wait_on_page(page)
        info = gtk.gdk.pixbuf_get_file_info(self.get_path_to_page(page))
        if info != None:
            return info[0]['name'].upper()
        return _('Unknown filetype')
    
    def get_thumbnail(self, page=None, width=128, height=128, create=False):
        
        """
        Returns a thumbnail pixbuf of <page> with dimensions <width>x<height>.
        Returns a thumbnail for the current page if <page> is None.
        If <create> is True, and the <width>x<height> <= 128x128, the 
        thumbnail is stored on disk.        
        """
        
        self._wait_on_page(page)
        path = self.get_path_to_page(page)
        if width <= 128 and height <= 128:
            thumb = thumbnail.get_thumbnail(path, create)
        else:
            try:
                thumb = gtk.gdk.pixbuf_new_from_file_at_size(path, width,
                    height)
            except:
                thumb = None
        if thumb == None:
            thumb = self._get_missing_image()
        thumb = image.fit_in_rectangle(thumb, width, height)
        return thumb
    
    def get_stats(self, page=None):
        
        """
        Returns a stat object as used by the Python stat module for <page>.
        If <page> is None return a stat object for the current page.
        Returns None if the stat object can not be produced (e.g. broken file).
        """
        
        self._wait_on_page(page)
        try:
            stats = os.stat(self.get_path_to_page(page))
        except:
            stats = None
        return stats

    def _wait_on_page(self, page):
        
        """
        Blocks the running (main) thread until the file corresponding to 
        <page> has been fully extracted.
        """
        
        # We don't have to wait for files not in an archive
        if not self.archive_type:
            return
        if page == None:
            page = self.get_current_page()
        self._condition.acquire()
        while not self._extractor.is_ready(page - 1):
            self._condition.wait()
        self._condition.release()

    def _wait_on_comment(self, num):
        pass


def thread_delete(path):
    
    """
    Starts a threaded removal of the directory tree rooted at <path>.
    This is to avoid long blockings when removing large temporary dirs.
    """
    
    del_thread = threading.Thread(target=shutil.rmtree, args=(path,))
    del_thread.setDaemon(False)
    del_thread.start()

def is_image_file(path):
    
    ''' Returns the mime type if <path> is an image file in a
    supported format, else False.
    '''
    
    if os.path.isfile(path): 
        info = gtk.gdk.pixbuf_get_file_info(path)
        if (info != None and info[0]['mime_types'][0]
            in ['image/jpeg', 'image/bmp', 'image/gif',
            'image/png', 'image/tiff', 'image/x-icon',
            'image/x-xpixmap', 'image/x-xbitmap', 'image/svg+xml',
            'image/svg', 'image/svg-xml', 'image/vnd.adobe.svg+xml',
            'text/xml-svg', 'image/x-portable-anymap',
            'image/x-portable-bitmap', 'image/x-portable-graymap',
            'image/x-portable-pixmap', 'image/x-pcx',
            'image/x-cmu-raster', 'image/x-sun-raster', 
            'image/x-tga']):
                return info[0]['mime_types'][0]
    return False

