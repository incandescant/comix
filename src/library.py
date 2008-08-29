"""library.py - Comic book library."""

import gtk
import gobject
import pango
import Image
import ImageDraw

import archive
import encoding
import filechooser
import librarybackend
from preferences import prefs
import image

_dialog = None
_COLLECTION_ALL = -1


class _LibraryDialog(gtk.Window):

    def __init__(self, file_handler):
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_size_request(400, 300)
        self.resize(prefs['lib window width'], prefs['lib window height'])
        self.set_title(_('Library'))
        self.connect('delete_event', self.close)

        self._file_handler = file_handler
        
        self.backend = librarybackend.LibraryBackend()
        self.book_area = _BookArea(self)
        self.collection_area = _CollectionArea(self)
        self._statusbar = gtk.Statusbar()
        self._statusbar.set_has_resize_grip(True)

        # The bottom box
        bottombox = gtk.HBox(False, 20)
        bottombox.set_border_width(10)
        borderbox = gtk.EventBox()
        borderbox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('#333'))
        borderbox.set_size_request(300, -1)
        insidebox = gtk.EventBox()
        insidebox.set_border_width(1)
        insidebox.modify_bg(gtk.STATE_NORMAL, gtk.gdk.color_parse('#ddb'))
        infobox = gtk.VBox(False, 5)
        infobox.set_border_width(10)
        bottombox.pack_start(borderbox, False, False)
        borderbox.add(insidebox)
        insidebox.add(infobox)
        self._namelabel = gtk.Label()
        self._namelabel.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self._namelabel.set_alignment(0, 0.5)
        infobox.pack_start(self._namelabel, False, False)
        self._typelabel = gtk.Label()
        self._typelabel.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self._typelabel.set_alignment(0, 0.5)
        infobox.pack_start(self._typelabel, False, False)
        self._pageslabel = gtk.Label()
        self._pageslabel.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self._pageslabel.set_alignment(0, 0.5)
        infobox.pack_start(self._pageslabel, False, False)
        self._sizelabel = gtk.Label()
        self._sizelabel.set_ellipsize(pango.ELLIPSIZE_MIDDLE)
        self._sizelabel.set_alignment(0, 0.5)
        infobox.pack_start(self._sizelabel, False, False)
        vbox = gtk.VBox(False, 10)
        bottombox.pack_start(vbox, True, True)
        hbox = gtk.HBox(False, 10)
        vbox.pack_start(hbox, False, False)
        self._search_entry = gtk.Entry()
        label = gtk.Label('%s:' % _('Search'))
        hbox.pack_start(label, False, False)
        hbox.pack_start(self._search_entry)
        vbox.pack_start(gtk.HBox(), True, True)
        hbox = gtk.HBox(False, 10)
        vbox.pack_start(hbox, False, False)
        add_book_button = gtk.Button(_('Add books'))
        add_book_button.set_image(gtk.image_new_from_stock(
            gtk.STOCK_ADD, gtk.ICON_SIZE_BUTTON))
        add_book_button.connect('clicked', self._open_add_dialog)
        hbox.pack_start(add_book_button, False, False)
        add_collection_button = gtk.Button(_('Add collection'))
        add_collection_button.set_image(gtk.image_new_from_stock(
            gtk.STOCK_ADD, gtk.ICON_SIZE_BUTTON))
        hbox.pack_start(add_collection_button, False, False)
        hbox.pack_start(gtk.HBox(), True, True)
        open_button = gtk.Button(None, gtk.STOCK_OPEN)
        #open_button.connect()
        hbox.pack_start(open_button, False, False)

        table = gtk.Table(2, 2, False)
        table.attach(self.collection_area, 0, 1, 0, 1, gtk.FILL,
            gtk.EXPAND|gtk.FILL)
        table.attach(self.book_area, 1, 2, 0, 1, gtk.EXPAND|gtk.FILL,
            gtk.EXPAND|gtk.FILL)
        table.attach(bottombox, 0, 2, 1, 2, gtk.EXPAND|gtk.FILL, gtk.FILL)
        table.attach(self._statusbar, 0, 2, 2, 3, gtk.FILL, gtk.FILL)
        self.add(table)

        self.show_all()

    def open_book(self, book):
        """Open the book with ID <book>."""
        info = self.backend.get_detailed_book_info(book)
        path = info[2]
        self.close()
        self._file_handler.open_file(path)

    def update_info(self, iconview):
        """Update the info box using the currently selected book."""
        selected = iconview.get_selected_items()
        if not selected:
            return
        path = selected[0]
        book = self.book_area.get_book_at_path(path)
        info = self.backend.get_detailed_book_info(book)
        self._namelabel.set_text(info[1])
        attrlist = pango.AttrList()
        attrlist.insert(pango.AttrWeight(pango.WEIGHT_BOLD, 0,
            len(self._namelabel.get_text())))
        self._namelabel.set_attributes(attrlist)
        self._typelabel.set_text(archive.get_name(info[4]))
        self._pageslabel.set_text(_('%d pages') % info[3])
        self._sizelabel.set_text('%.1f MiB' % (info[5] / 1048576.0))
                
    def set_status_message(self, message):
        """Set a specific message on the statusbar, replacing whatever was
        there earlier.
        """
        self._statusbar.pop(0)
        self._statusbar.push(0, ' %s' % encoding.to_unicode(message))

    def close(self, *args):
        """Close the library and do required cleanup tasks."""
        prefs['lib window width'], prefs['lib window height'] = self.get_size()
        self.book_area.stop_update()
        self.backend.close()
        _close_dialog()

    def _open_add_dialog(self, *args):
        """Open up a dialog where books can be added to the library."""
        filechooser.open_library_filechooser_dialog(self)

    def add_books(self, paths):
        """Add the books at the filesystem paths in the sequence <paths>
        to the library."""
        print paths


class _CollectionArea(gtk.ScrolledWindow):
    
    """The _CollectionArea is the sidebar area in the library where
    different collections are displayed in a tree.
    """
    
    def __init__(self, library):
        gtk.ScrolledWindow.__init__(self)
        self._library = library
        self.set_policy(gtk.POLICY_NEVER, gtk.POLICY_AUTOMATIC)

        self._treestore = gtk.TreeStore(str, int)
        self._treeview = gtk.TreeView(self._treestore)
        self._treeview.connect('cursor_changed', self._collection_selected)
        self._treeview.connect('drag_data_received', self._drag_book_end)
        self._treeview.connect('drag_motion', self._drag_book_motion)
        self._treeview.connect('button_press_event', self._button_press)
        self._treeview.set_headers_visible(False)
        self._treeview.set_rules_hint(True)
        self._treeview.enable_model_drag_dest(
            [('book', gtk.TARGET_SAME_APP, 0)], gtk.gdk.ACTION_MOVE)
        #self._treeview.set_reorderable(True)
        cellrenderer = gtk.CellRendererText()
        column = gtk.TreeViewColumn(None, cellrenderer, markup=0)
        self._treeview.append_column(column)
        self.add(self._treeview)
        
        self._ui_manager = gtk.UIManager()
        ui_description = """
        <ui>
            <popup name="Popup">
                <menuitem action="rename" />
                <menuitem action="duplicate" />
                <separator />
                <menuitem action="remove" />
            </popup>
        </ui>
        """
        self._ui_manager.add_ui_from_string(ui_description)
        actiongroup = gtk.ActionGroup('comix-library-collection-area')
        actiongroup.add_actions([
        ('rename', None, _('Rename'), None, None, None),
        ('duplicate', gtk.STOCK_COPY, _('Duplicate collection'), None, None,
            None),
        ('remove', gtk.STOCK_REMOVE, _('Remove collection...'), None, None,
            self._remove_collection)])
        self._ui_manager.insert_action_group(actiongroup, 0)
        
        self._display_collections()
        self._treestore.foreach(self._select_last_collection)

    def get_current_collection(self):
        """Return the collection ID for the currently selected collection,
        or None if no collection is selected."""
        cursor = self._treeview.get_cursor()
        if cursor is None:
            return
        return self._get_collection_at_path(cursor[0])

    def _get_collection_at_path(self, path):
        """Return the collection ID of the collection at the (TreeView)
        <path>."""
        iterator = self._treestore.get_iter(path)
        return self._treestore.get_value(iterator, 1)

    def _collection_selected(self, treeview):
        """Change the viewed collection (in the _BookArea) to the
        currently selected one in the sidebar."""
        collection = self.get_current_collection()
        if (collection is None or
          collection == prefs['last library collection']):
            return
        prefs['last library collection'] = collection
        if collection == _COLLECTION_ALL:
            collection = None
        gobject.idle_add(self._library.book_area.display_covers, collection)

    def _display_collections(self):
        """Display the library collections. Should be called on startup."""
        
        def _add(parent_iter, supercoll):
            for coll in self._library.backend.get_collections_in_collection(
              supercoll):
                child_iter = self._treestore.append(parent_iter,
                    [coll[1], coll[0]])
                _add(child_iter, coll[0])

        self._treestore.clear()
        self._treestore.append(None, ['<b>%s</b>' % _('All books'),
            _COLLECTION_ALL])
        _add(None, None)

    def _select_last_collection(self, treestore, path, iterator):
        """Select the collection that was selected the last time the library
        was used. Should be used with TreeModel.foreach()."""
        collection = treestore.get_value(iterator, 1)
        if collection == prefs['last library collection']:
            prefs['last library collection'] = False # Reset to trigger update
            self._treeview.expand_to_path(path)
            self._treeview.set_cursor(path)
            return True

    def _remove_collection(self, action):
        """Remove the cuurently selected collection from the library, if the
        user answers 'Yes' in a dialog."""
        choice_dialog = gtk.MessageDialog(None, 0, gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_YES_NO, _('Remove collection from the library?'))
        choice_dialog.format_secondary_text(
            _('The selected collection will be removed from the library (but the books and subcollections in it will remain). Are you sure that you want to continue?'))
        response = choice_dialog.run()
        choice_dialog.destroy()
        if response == gtk.RESPONSE_YES:
            collection = self.get_current_collection()
            self._library.backend.remove_collection(collection)
            self._display_collections()
            prefs['last library collection'] = _COLLECTION_ALL
            self._treestore.foreach(self._select_last_collection)

    def _button_press(self, treeview, event):
        """Handle mouse button presses on the _CollectionArea."""
        pos_tuple = treeview.get_path_at_pos(int(event.x), int(event.y))
        if pos_tuple is None:
            return
        path = pos_tuple[0]
        if event.button == 3:
            if self._get_collection_at_path(path) == _COLLECTION_ALL:
                sens = False
            else:
                sens = True
            self._ui_manager.get_action('/Popup/rename').set_sensitive(sens)
            self._ui_manager.get_action('/Popup/remove').set_sensitive(sens)
            self._ui_manager.get_widget('/Popup').popup(None, None, None,
                event.button, event.time)

    def _drag_book_end(self, treeview, context, x, y, selection, *args):
        """Move books dragged from the _BookArea to the target collection."""
        self._library.set_status_message('')
        src_collection, dest_collection = \
            self._drag_get_src_and_dest_collections(treeview, x, y)
        if src_collection == dest_collection:
            return
        for path_string in selection.get_text().split(','):
            book = self._library.book_area.get_book_at_path(int(path_string))
            if src_collection != _COLLECTION_ALL:
                self._library.backend.remove_book_from_collection(book,
                    src_collection)
                self._library.book_area.remove_book_at_path(int(path_string))
            if dest_collection != _COLLECTION_ALL:
                self._library.backend.add_book_to_collection(book,
                    dest_collection)

    def _drag_book_motion(self, treeview, context, x, y, *args):
        """Set the library statusbar text when hovering a drag-n-drop
        over a collection."""
        src_collection, dest_collection = \
            self._drag_get_src_and_dest_collections(treeview, x, y)
        if src_collection == dest_collection:
            self._library.set_status_message('')
            return
        if src_collection != _COLLECTION_ALL:
            src_name = self._library.backend.get_detailed_collection_info(
                src_collection)[1]
        if dest_collection != _COLLECTION_ALL:
            dest_name = self._library.backend.get_detailed_collection_info(
                dest_collection)[1]
        if dest_collection == _COLLECTION_ALL:
            message = _('Remove book(s) from "%s".') % src_name
        elif src_collection == _COLLECTION_ALL:
            message = _('Add book(s) to "%s".') % dest_name
        else:
            message = _('Move book(s) from "%s" to "%s".') % (src_name,
                dest_name)
        self._library.set_status_message(message)
        
    def _drag_get_src_and_dest_collections(self, treeview, x, y):
        """Convenience function to get the IDs for the source and
        destination collections during a drag-n-drop."""
        src_collection = self.get_current_collection()
        drop_row = treeview.get_dest_row_at_pos(x, y)
        if src_collection is None or drop_row is None:
            return 0, 0
        dest_collection = self._get_collection_at_path(drop_row[0])
        return src_collection, dest_collection


class _BookArea(gtk.ScrolledWindow):
    
    """The _BookArea is the central area in the library where the book
    covers are displayed.
    """
    
    def __init__(self, library):
        gtk.ScrolledWindow.__init__(self)
        self._library = library
        self._stop_update = False
        self.set_policy(gtk.POLICY_AUTOMATIC, gtk.POLICY_AUTOMATIC)
        
        self._liststore = gtk.ListStore(gtk.gdk.Pixbuf, int)
        self._iconview = gtk.IconView(self._liststore)
        self._iconview.set_pixbuf_column(0)
        self._iconview.connect('item_activated', self._book_activated)
        self._iconview.connect('selection_changed', self._library.update_info)
        self._iconview.connect_after('drag_begin', self._drag_begin)
        self._iconview.connect('drag_data_get', self._drag_data_get)
        self._iconview.connect('button_press_event', self._button_press)
        self._iconview.modify_base(gtk.STATE_NORMAL, gtk.gdk.Color())
        self._iconview.enable_model_drag_source(0,
            [('book', gtk.TARGET_SAME_APP, 0)], gtk.gdk.ACTION_MOVE)
        self._iconview.set_selection_mode(gtk.SELECTION_MULTIPLE)
        self.add(self._iconview)
        
        self._ui_manager = gtk.UIManager()
        ui_description = """
        <ui>
            <popup name="Popup">
                <menuitem action="open" />
                <separator />
                <menuitem action="remove from collection" />
                <menuitem action="remove from library" />
            </popup>
        </ui>
        """
        self._ui_manager.add_ui_from_string(ui_description)
        actiongroup = gtk.ActionGroup('comix-library-book-area')
        actiongroup.add_actions([
        ('open', gtk.STOCK_OPEN, _('Open'), None, None,
            self._open_selected_book),
        ('remove from collection', gtk.STOCK_REMOVE,
            _('Remove from this collection'), None, None,
            self._remove_books_from_collection),
        ('remove from library', gtk.STOCK_DELETE,
            _('Remove from library...'), None, None,
            self._remove_books_from_library)])
        self._ui_manager.insert_action_group(actiongroup, 0)

    def display_covers(self, collection):
        """Display the books in <collection> in the IconView."""
        self._stop_update = False
        self._liststore.clear()
        for i, book in enumerate(self._library.backend.get_books_in_collection(
          collection)):
            pixbuf = self._library.backend.get_book_cover(book[0])
            if pixbuf is None:
                continue
            pixbuf = image.fit_in_rectangle(pixbuf,
                int(0.67 * prefs['library cover size']),
                prefs['library cover size'])
            pixbuf = image.add_border(pixbuf, 2, 0xFFFFFFFF)
            self._liststore.append([pixbuf, book[0]])
            if i % 15 == 0: # Don't update GUI for every cover for efficiency.
                while gtk.events_pending():
                    gtk.main_iteration(False)
                if self._stop_update:
                    return
        self._stop_update = True

    def stop_update(self):
        """Signal that the updating of book covers should stop."""
        self._stop_update = True

    def remove_book_at_path(self, path):
        """Remove the book at <path> from the ListStore (and thus from
        the _BookArea)."""
        iterator = self._liststore.get_iter(path)
        self._liststore.remove(iterator)

    def get_book_at_path(self, path):
        """Return the book ID corresponding to the IconView <path>."""
        iterator = self._liststore.get_iter(path)
        return self._liststore.get_value(iterator, 1)

    def _open_selected_book(self, *args):
        """Open the currently selected book."""
        path = self._iconview.get_selected_items()[0]
        self._book_activated(self._iconview, path)

    def _book_activated(self, iconview, path):
        """Open the book at the (liststore) <path>."""
        book = self.get_book_at_path(path)
        self._library.open_book(book)

    def _remove_books_from_collection(self, *args):
        """Remove the currently selected book(s) from the current collection,
        and thus also from the _BookArea."""
        selected = self._iconview.get_selected_items()
        for path in selected:
            book = self.get_book_at_path(path)
            collection = self._library.collection_area.get_current_collection()
            self._library.backend.remove_book_from_collection(book, collection)
            self.remove_book_at_path(path)
        coll_name = self._library.backend.get_detailed_collection_info(
            collection)[1]
        self._library.set_status_message(
            _('Removed %d book(s) from "%s".') % (len(selected), coll_name))

    def _remove_books_from_library(self, *args):
        """Remove the currently selected book(s) from the library, and thus
        also from the _BookArea, if the user clicks 'Yes' in a dialog."""
        choice_dialog = gtk.MessageDialog(None, 0, gtk.MESSAGE_QUESTION,
            gtk.BUTTONS_YES_NO, _('Remove book(s) from the library?'))
        choice_dialog.format_secondary_text(
            _('The selected books will be removed from the library (but the comic book files will be untouched). Are you sure that you want to continue?'))
        response = choice_dialog.run()
        choice_dialog.destroy()
        if response == gtk.RESPONSE_YES:
            selected = self._iconview.get_selected_items()
            for path in selected:
                book = self.get_book_at_path(path)
                self._library.backend.remove_book(book)
                self.remove_book_at_path(path)
            self._library.set_status_message(
                _('Removed %d book(s) from the library.') % len(selected))

    def _button_press(self, iconview, event):
        """Handle mouse button presses on the _BookArea."""
        path = iconview.get_path_at_pos(int(event.x), int(event.y))
        if path is None:
            return
        if event.button == 3:
            if not iconview.path_is_selected(path):
                iconview.unselect_all()
                iconview.select_path(path)
            if len(iconview.get_selected_items()) > 1:
                self._ui_manager.get_action('/Popup/open').set_sensitive(False)
            else:
                self._ui_manager.get_action('/Popup/open').set_sensitive(True)
            if (self._library.collection_area.get_current_collection() ==
              _COLLECTION_ALL):
                self._ui_manager.get_action(
                    '/Popup/remove from collection').set_sensitive(False)
            else:
                self._ui_manager.get_action(
                    '/Popup/remove from collection').set_sensitive(True)
            self._ui_manager.get_widget('/Popup').popup(None, None, None,
                event.button, event.time)
        
    def _drag_begin(self, iconview, context):
        """Create a cursor image for drag n drop from the library.

        This method relies on implementation details regarding PIL's 
        drawing functions and default font to produce good looking results.
        If those are changed in a future release of PIL, this method might
        produce bad looking output (e.g. non-centered text).
        
        It's also used with connect_after() to overwrite the cursor
        automatically created when using enable_model_drag_source(), so in
        essence it's a hack, but at least it works."""
        selected = iconview.get_selected_items()
        icon_path = selected[-1]
        num_books = len(selected)
        book = self.get_book_at_path(icon_path)

        cover = self._library.backend.get_book_cover(book)
        cover = cover.scale_simple(cover.get_width() // 2,
            cover.get_height() // 2, gtk.gdk.INTERP_TILES)
        cover = image.add_border(cover, 1, 0xFFFFFFFF)
        cover = image.add_border(cover, 1)
        
        if num_books > 1:
            pointer = gtk.gdk.Pixbuf(gtk.gdk.COLORSPACE_RGB, True, 8, 100, 100)
            pointer.fill(0x00000000)
            cover_width = cover.get_width()
            cover_height = cover.get_height()
            cover.composite(pointer, 0, 0, cover_width, cover_height, 0, 0,
            1, 1, gtk.gdk.INTERP_TILES, 255)
            im = Image.new('RGBA', (30, 30), 0x00000000)
            draw = ImageDraw.Draw(im)
            draw.ellipse((0, 0, 29, 29), outline=(0, 0, 0), fill=(128, 0, 0))
            draw = ImageDraw.Draw(im)
            text = str(num_books)
            draw.text((15 - (6 * len(text) // 2), 9), text,
                fill=(255, 255, 255))
            circle = image.pil_to_pixbuf(im)
            circle.composite(pointer, cover_width - 15, cover_height - 20,
                29, 29, cover_width - 15, cover_height - 20, 1, 1,
                gtk.gdk.INTERP_TILES, 255)
        else:
            pointer = cover

        context.set_icon_pixbuf(pointer, -5, -5)

    def _drag_data_get(self, iconview, context, selection, *args):
        """Fill the SelectionData with (iconview) paths for the dragged books
        formatted as a string with each path separated by a comma."""
        paths = iconview.get_selected_items()
        text = ','.join([str(path[0]) for path in paths])
        selection.set('text/plain', 8, text)
        

def open_dialog(action, window):
    global _dialog
    if _dialog is None:
        if librarybackend.dbapi2 is None:
            print '! You need an sqlite wrapper to use the library.'
        else:
            _dialog = _LibraryDialog(window)
    else:
        _dialog.present()


def _close_dialog(*args):
    global _dialog
    if _dialog is not None:
        _dialog.destroy()
        _dialog = None
