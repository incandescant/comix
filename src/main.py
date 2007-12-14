# ============================================================================
# main.py - Main window and logic for Comix.
# ============================================================================

import sys
import os
import shutil
import time

import gtk

import filehandler
import preferences
import icons
import ui
import thumbbar
import scale
import event
import pilpixbuf

window = None

class MainWindow(gtk.Window):
    
    def __init__(self): 
        gtk.Window.__init__(self, gtk.WINDOW_TOPLEVEL)
        self.set_title('Comix')
        
        self.is_fullscreen = False
        self.double_page = False 
        self.manga_mode = False
        self.zoom_mode = 'fit'
        self.manual_zoom = 100
        self.rotation = 0
        self.keep_rotation = False

        self.realize()
        if preferences.prefs['save window pos']:
            self.move(preferences.prefs['window x'],
                      preferences.prefs['window y'])
        self.set_size_request(300, 300) # Avoid making the window *too* small
        self.resize(preferences.prefs['window width'],
                    preferences.prefs['window height'])
        self.width, self.height = self.get_size()
        
        # ----------------------------------------------------------------
        # Create and initialize widgets for the main window.
        # ----------------------------------------------------------------
        self.left_image = gtk.Image()
        self.right_image = gtk.Image()
        self.comment_label = gtk.Label()
        self.statusbar = gtk.Statusbar()
        self.main_layout = gtk.Layout()
        self.thumbnailsidebar = thumbbar.ThumbnailSidebar()
        self.ui_manager = ui.MainUI()
        self.add_accel_group(self.ui_manager.get_accel_group())
        self.actiongroup = self.ui_manager.get_action_groups()[0]
        self.menubar = self.ui_manager.get_widget('/Menu')
        self.toolbar = self.ui_manager.get_widget('/Tool')
        # This is a hack to get the focus away from the toolbar so that
        # we don't activate it with space or some other key.
        self.toolbar.set_focus_child(
            self.ui_manager.get_widget('/Tool/expander'))

        self.image_box = gtk.HBox(False, 2)
        self.image_box.add(self.left_image)
        self.image_box.add(self.right_image)
        self.image_box.show_all()
        
        self.main_layout.put(self.image_box, 0, 0)
        self.main_layout.put(self.comment_label, 0, 0)
        self.main_layout.modify_bg(gtk.STATE_NORMAL,
            gtk.gdk.colormap_get_system().alloc_color(gtk.gdk.Color(
            preferences.prefs['red bg'], preferences.prefs['green bg'],
            preferences.prefs['blue bg']), False, True))

        # ----------------------------------------------------------------
        # Create scrollbar widgets.
        # ----------------------------------------------------------------
        self.vadjust = self.main_layout.get_vadjustment()
        self.hadjust = self.main_layout.get_hadjustment()
        self.vadjust.step_increment = 15
        self.vadjust.page_increment = 1
        self.hadjust.step_increment = 15
        self.hadjust.page_increment = 1
        self.hscroll = gtk.HScrollbar(self.hadjust)
        self.vscroll = gtk.VScrollbar(self.vadjust)
        
        # ----------------------------------------------------------------
        # Attach widgets to the main table.
        # ----------------------------------------------------------------
        self.table = gtk.Table(2, 2, False)
        self.table.attach(self.thumbnailsidebar.layout, 0, 1, 2, 5, gtk.FILL,
                          gtk.FILL|gtk.EXPAND, 0, 0)
        self.table.attach(self.thumbnailsidebar.scroll, 1, 2, 2, 4,
                          gtk.FILL|gtk.SHRINK, gtk.FILL|gtk.SHRINK, 0, 0)
        self.table.attach(self.main_layout, 2, 3, 2, 3, gtk.FILL|gtk.EXPAND,
                          gtk.FILL|gtk.EXPAND, 0, 0)
        self.table.attach(self.vscroll, 3, 4, 2, 3, gtk.FILL|gtk.SHRINK,
                          gtk.FILL|gtk.SHRINK, 0, 0)
        self.table.attach(self.hscroll, 2, 3, 4, 5, gtk.FILL|gtk.SHRINK,
                          gtk.FILL, 0, 0)
        self.table.attach(self.toolbar, 0, 4, 1, 2, gtk.FILL|gtk.SHRINK,
                          gtk.FILL, 0, 0)
        self.table.attach(self.statusbar, 0, 4, 5, 6, gtk.FILL|gtk.SHRINK,
                          gtk.FILL, 0, 0)
        self.table.attach(self.menubar, 0, 4, 0, 1, gtk.FILL|gtk.SHRINK,
                          gtk.FILL, 0, 0)

        self.add(self.table)
        self.table.show()
        self.main_layout.show()
        self.display_active_widgets()

        self.main_layout.set_events(gtk.gdk.BUTTON1_MOTION_MASK |
                                    gtk.gdk.BUTTON2_MOTION_MASK | 
                                    gtk.gdk.BUTTON_RELEASE_MASK |
                                    gtk.gdk.POINTER_MOTION_MASK)

        self.connect('delete_event', terminate_program)
        self.connect('key_press_event', event.key_press_event)
        self.main_layout.connect('scroll_event', event.scroll_wheel_event)
        self.connect('configure_event', event.resize_event)
        self.main_layout.connect('button_press_event', event.mouse_press_event)
        self.connect('button_release_event', event.mouse_release_event)
        self.main_layout.connect('motion_notify_event', event.mouse_move_event)

    def display_active_widgets(self):
        if not preferences.prefs['hide all'] and not (self.is_fullscreen and 
          preferences.prefs['hide all in fullscreen']):
            if preferences.prefs['show toolbar']:
                self.toolbar.show_all()
            else:
                self.toolbar.hide_all()
            if preferences.prefs['show statusbar']:
                self.statusbar.show_all()
            else:
                self.statusbar.hide_all()
            if preferences.prefs['show thumbnails']:
                self.thumbnailsidebar.show()
            else:
                self.thumbnailsidebar.hide()
            if preferences.prefs['show menubar']:
                self.menubar.show_all()
            else:
                self.menubar.hide_all()
            if (preferences.prefs['show scrollbar'] and
              self.zoom_mode == 'width'):
                self.vscroll.show_all()
                self.hscroll.hide_all()
            elif (preferences.prefs['show scrollbar'] and
              self.zoom_mode == 'height'):
                self.vscroll.hide_all()
                self.hscroll.show_all()
            elif (preferences.prefs['show scrollbar'] and
              self.zoom_mode == 'manual'):
                self.vscroll.show_all()
                self.hscroll.show_all()
            else:
                self.vscroll.hide_all()
                self.hscroll.hide_all()
        else:
            self.toolbar.hide_all()
            self.menubar.hide_all()
            self.statusbar.hide_all()
            self.thumbnailsidebar.hide()
            self.vscroll.hide_all()
            self.hscroll.hide_all()

    def get_layout_size(self):
        width, height = self.get_size()
        if not preferences.prefs['hide all'] and not (self.is_fullscreen and 
          preferences.prefs['hide all in fullscreen']):
            if preferences.prefs['show toolbar']:
                height -= self.toolbar.size_request()[1]
            if preferences.prefs['show statusbar']:
                height -= self.statusbar.size_request()[1]
            if preferences.prefs['show thumbnails']:
                width -= self.thumbnailsidebar.get_width()
            if preferences.prefs['show menubar']:
                height -= self.menubar.size_request()[1]
            if (preferences.prefs['show scrollbar'] and
              self.zoom_mode == 'width'):
                width -= self.vscroll.size_request()[0]
            elif (preferences.prefs['show scrollbar'] and
              self.zoom_mode == 'height'):
                height -= self.hscroll.size_request()[1]
            elif (preferences.prefs['show scrollbar'] and
              self.zoom_mode == 'manual'):
                width -= self.vscroll.size_request()[0]
                height -= self.hscroll.size_request()[1]
        return width, height

    def draw_image(self, at_bottom=False):
        self.display_active_widgets()
        if not filehandler.file_loaded:
            self.left_image.clear()
            self.right_image.clear()
            self.thumbnailsidebar.clear()
            self.set_title('Comix')
            return
        print 'draw'
        width, height = self.get_layout_size()
        scale_width = self.zoom_mode == 'height' and -1 or width
        scale_height = self.zoom_mode == 'width' and -1 or height
        scale_up = preferences.prefs['stretch']
        
        if is_double():
            if self.manga_mode:
                right_pixbuf, left_pixbuf = filehandler.get_pixbufs()
            else:
                left_pixbuf, right_pixbuf = filehandler.get_pixbufs()

            if self.zoom_mode == 'manual':
                if self.rotation in [90, 270]:
                    scale_width = int(self.manual_zoom *
                        (left_pixbuf.get_height() +
                        right_pixbuf.get_height()) // 100)
                    scale_height = int(self.manual_zoom * max(
                        left_pixbuf.get_width(),
                        right_pixbuf.get_width()) // 100)
                else:
                    scale_width = int(self.manual_zoom * 
                        (left_pixbuf.get_width() +
                        right_pixbuf.get_width()) // 100)
                    scale_height = int(self.manual_zoom * max(
                        left_pixbuf.get_height(),
                        right_pixbuf.get_height()) // 100)
                
                scale_up = True

            left_pixbuf, right_pixbuf = scale.fit_2_in_rectangle(
                left_pixbuf, right_pixbuf, scale_width, scale_height,
                scale_up=scale_up, rotation=self.rotation)
            self.left_image.set_from_pixbuf(left_pixbuf)
            self.right_image.set_from_pixbuf(right_pixbuf)
            x_padding = (width - left_pixbuf.get_width() -
                right_pixbuf.get_width()) / 2
            y_padding = (height - max(left_pixbuf.get_height(),
                right_pixbuf.get_height())) / 2
            self.right_image.show()
        else:
            pixbuf = filehandler.get_pixbufs()

            if self.zoom_mode == 'manual':
                scale_width = int(self.manual_zoom * pixbuf.get_width() // 100)
                scale_height = int(self.manual_zoom * pixbuf.get_height()
                    // 100)
                if self.rotation in [90, 270]:
                    scale_width, scale_height = scale_height, scale_width
                scale_up = True

            pixbuf = scale.fit_in_rectangle(pixbuf, scale_width, scale_height,
                scale_up=scale_up, rotation=self.rotation)

            #im = pilpixbuf.pixbuf_to_pil(pixbuf)
            #pixbuf = pilpixbuf.pil_to_pixbuf(im)

            self.left_image.set_from_pixbuf(pixbuf)
            self.right_image.clear()
            self.right_image.hide()
            x_padding = (width - pixbuf.get_width()) / 2
            y_padding = (height - pixbuf.get_height()) / 2
        
        self.main_layout.move(self.image_box, max(0, x_padding),
            max(0, y_padding))
        self.main_layout.set_size(*self.image_box.size_request())
        if at_bottom:
            self.vadjust.set_value(self.vadjust.upper - height)
            if self.manga_mode:
                self.hadjust.set_value(0)
            else:
                self.hadjust.set_value(self.hadjust.upper - width)
        else:
            self.vadjust.set_value(0)
            if self.manga_mode:
                self.hadjust.set_value(self.hadjust.upper - width)
            else:
                self.hadjust.set_value(0)
        
        self.set_title(os.path.basename(filehandler.archive_path) + 
            '  [%d / %d]  -  Comix' % (filehandler.current_image + 1,
            len(filehandler.image_files)))

        while gtk.events_pending():
            gtk.main_iteration(False)
        filehandler.do_cacheing()

def next_page(*args):
    if filehandler.next_page():
        if not window.keep_rotation:
            window.rotation = 0
        window.thumbnailsidebar.update_select()
        window.draw_image()

def previous_page(*args):
    if filehandler.previous_page():
        if not window.keep_rotation:
            window.rotation = 0
        window.thumbnailsidebar.update_select()
        window.draw_image(at_bottom=True)

def first_page(*args):
    if filehandler.first_page():
        if not window.keep_rotation:
            window.rotation = 0
        window.thumbnailsidebar.update_select()
        window.draw_image()

def last_page(*args):
    if filehandler.last_page():
        if not window.keep_rotation:
            window.rotation = 0
        window.thumbnailsidebar.update_select()
        window.draw_image()

def set_page(num):
    if filehandler.set_page(num):
        if not window.keep_rotation:
            window.rotation = 0
        window.thumbnailsidebar.update_select()
        window.draw_image()

def rotate90(*args):
    window.rotation = (window.rotation + 90) % 360
    window.draw_image()

def rotate180(*args):
    window.rotation = (window.rotation + 180) % 360
    window.draw_image()

def rotate270(*args):
    window.rotation = (window.rotation + 270) % 360
    window.draw_image()

def change_double_page(toggleaction):
    window.double_page = toggleaction.get_active()
    window.draw_image()

def change_manga_mode(toggleaction):
    window.manga_mode = toggleaction.get_active()
    window.draw_image()

def change_zoom_mode(radioaction, *args):
    mode = radioaction.get_current_value()
    old_mode = window.zoom_mode
    if mode == 0:
        window.zoom_mode = 'manual'
    elif mode == 1:
        window.zoom_mode = 'fit'
    elif mode == 2:
        window.zoom_mode = 'width'
    else:
        window.zoom_mode = 'height'
    if old_mode != window.zoom_mode:
        window.draw_image()

def change_fullscreen(toggleaction):
    window.is_fullscreen = toggleaction.get_active()
    if window.is_fullscreen:
        window.fullscreen()
    else:
        window.unfullscreen()

def change_toolbar_visibility(*args):
    preferences.prefs['show toolbar'] = \
        not preferences.prefs['show toolbar']
    window.draw_image()

def change_menubar_visibility(*args):
    preferences.prefs['show menubar'] = \
        not preferences.prefs['show menubar']
    window.draw_image()

def change_statusbar_visibility(*args):
    preferences.prefs['show statusbar'] = \
        not preferences.prefs['show statusbar']
    window.draw_image()

def change_scrollbar_visibility(*args):
    preferences.prefs['show scrollbar'] = \
        not preferences.prefs['show scrollbar']
    window.draw_image()

def change_thumbnails_visibility(*args):
    preferences.prefs['show thumbnails'] = \
        not preferences.prefs['show thumbnails']
    window.draw_image()

def change_hide_all(*args):
    preferences.prefs['hide all'] = not preferences.prefs['hide all']
    window.draw_image()

def change_keep_rotation(*args):
    window.keep_rotation = not window.keep_rotation

def manual_zoom_in(*args):
    new_zoom = window.manual_zoom * 1.15
    if 95 < new_zoom < 105: # To compensate for rounding errors
        new_zoom = 100
    if new_zoom > 1000:
        return
    window.manual_zoom = new_zoom
    window.draw_image()

def manual_zoom_out(*args):
    new_zoom = window.manual_zoom / 1.15
    if 95 < new_zoom < 105: # To compensate for rounding errors
        new_zoom = 100
    if new_zoom < 10:
        return
    window.manual_zoom = new_zoom
    window.draw_image()

def manual_zoom_original(*args):
    window.manual_zoom = 100
    window.draw_image()

def scroll(x, y):

    """
    Scrolls <x> px horizontally and <y> px vertically.
    Returns True if call resulted in new adjustment values, False otherwise.
    """

    old_hadjust = window.hadjust.get_value()
    old_vadjust = window.vadjust.get_value()
    layout_width, layout_height = window.get_layout_size()
    hadjust_upper = window.hadjust.upper - layout_width
    vadjust_upper = window.vadjust.upper - layout_height
    new_hadjust = old_hadjust + x
    new_vadjust = old_vadjust + y
    new_hadjust = max(0, new_hadjust)
    new_vadjust = max(0, new_vadjust)
    new_hadjust = min(hadjust_upper, new_hadjust)
    new_vadjust = min(vadjust_upper, new_vadjust)
    window.vadjust.set_value(new_vadjust)
    window.hadjust.set_value(new_hadjust)
    return old_vadjust != new_vadjust or old_hadjust != new_hadjust

def scroll_to_fixed(horiz=None, vert=None):
    
    """
    If either <horiz> or <vert> is not None, the display is scrolled as
    follows:

    horiz: 'left'        = left end of display
           'middle'      = middle of the display
           'right'       = rigth end of display
           'startfirst'  = start of first page
           'endfirst'    = end of first page
           'startsecond' = start of second page
           'endsecond'   = end of second page
    
    vert:  'top'         = top of display
           'middle'      = middle of display
           'bottom'      = bottom of display

    Scrolling to the second page is, of course, only applicable in double
    page mode. What is considered "start" and "end" depends on whether we
    are using manga mode or not.
    """

    layout_width, layout_height = window.get_layout_size()
    vadjust_upper = window.vadjust.upper - layout_height
    hadjust_upper = window.hadjust.upper - layout_width

    if vert == 'top':
        window.vadjust.set_value(0)
    elif vert == 'middle':
        window.vadjust.set_value(vadjust_upper / 2)
    elif vert == 'bottom':
        window.vadjust.set_value(vadjust_upper)
    
    # Manga transformations.
    if window.manga_mode and is_double():
        horiz = {'left':        'left',
                 'middle':      'middle',
                 'right':       'right',
                 'startfirst':  'endsecond',
                 'endfirst':    'startsecond',
                 'startsecond': 'endfirst',
                 'endsecond':   'startfirst'}[horiz]
    elif window.manga_mode:
        horiz = {'left':        'left',
                 'middle':      'middle',
                 'right':       'right',
                 'startfirst':  'endfirst',
                 'endfirst':    'startfirst'}[horiz]
    
    if horiz == 'left':
        window.hadjust.set_value(0)
    elif horiz == 'middle':
        window.hadjust.set_value(hadjust_upper / 2)
    elif horiz == 'right':
        window.hadjust.set_value(hadjust_upper)
    elif horiz == 'startfirst':
        window.hadjust.set_value(0)
    elif horiz == 'endfirst':
        if is_double():
            window.hadjust.set_value(
                window.left_image.size_request()[0] - layout_width)
        else:
            window.hadjust.set_value(hadjust_upper)
    elif horiz == 'startsecond':
        window.hadjust.set_value(window.left_image.size_request()[0] + 2)
    elif horiz == 'endsecond':
        window.hadjust.set_value(vadjust_upper)

def is_double():
    return window.double_page and not filehandler.is_last_page()

def terminate_program(*args):
    
    """ Runs clean-up tasks and exits the program. """

    print 'Bye!'
    gtk.main_quit()
    shutil.rmtree(filehandler.tmp_dir)
    sys.exit(0)

def start():

    """ Runs setup tasks and starts the main loop. """

    global window
    window = MainWindow()
    window.show()
    if preferences.prefs['default double page']:
        window.actiongroup.get_action('double').activate()
    if preferences.prefs['default fullscreen']:
        window.actiongroup.get_action('fullscreen').activate()
    if preferences.prefs['default manga mode']:
        window.actiongroup.get_action('manga_mode').activate()
    if preferences.prefs['default zoom mode'] == 'manual':
        window.actiongroup.get_action('fit_manual_mode').activate()
    elif preferences.prefs['default zoom mode'] == 'fit':
        window.actiongroup.get_action('fit_screen_mode').activate()
    elif preferences.prefs['default zoom mode'] == 'width':
        window.actiongroup.get_action('fit_width_mode').activate()
    else:
        window.actiongroup.get_action('fit_height_mode').activate()
    if preferences.prefs['show toolbar']:
        preferences.prefs['show toolbar'] = False
        window.actiongroup.get_action('toolbar').activate()
    if preferences.prefs['show menubar']:
        preferences.prefs['show menubar'] = False
        window.actiongroup.get_action('menubar').activate()
    if preferences.prefs['show statusbar']:
        preferences.prefs['show statusbar'] = False
        window.actiongroup.get_action('statusbar').activate()
    if preferences.prefs['show scrollbar']:
        preferences.prefs['show scrollbar'] = False
        window.actiongroup.get_action('scrollbar').activate()
    if preferences.prefs['show thumbnails']:
        preferences.prefs['show thumbnails'] = False
        window.actiongroup.get_action('thumbnails').activate()
    if preferences.prefs['hide all']:
        preferences.prefs['hide all'] = False
        window.actiongroup.get_action('hide all').activate()
    gtk.main()

