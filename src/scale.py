import gtk

import preferences

def fit_in_rectangle(src, width, height, interp=None, scale_up=False):
    
    ''' Returns a pixbuf scaled from <src> to fit into a rectangle with
    dimensions <width> x <height>. A negative <width> or <height> means an
    unbounded dimension, both can not be negative.
    
    If <interp> is set it is used as the scaling method, otherwise the
    default value from preferences is used.
    
    Unless <scale_up> is True we don't stretch images smaller than the
    given rectangle.

    If <src> has an alpha channel it gets a checkboard background.
    '''
    
    # "Unbounded" really means "bounded to 10000 px", for simplicity.
    # Comix would choke on larger images anyway.
    if width < 0:
        width = 10000
    elif height < 0:
        height = 10000

    if not scale_up and src.get_width() <= width and src.get_height() <= height:
        if src.get_has_alpha():
            return src.composite_color_simple(src.get_width(), src.get_height(),
                gtk.gdk.INTERP_TILES, 255, 8, 0x777777, 0x999999)
        else:
            return src

    if float(src.get_width()) / width > float(src.get_height()) / height:
        height = src.get_height() * width / src.get_width()
    else:
        width = src.get_width() * height / src.get_height()

    if interp == None:
        interp = preferences.prefs['interp mode']
    
    if src.get_has_alpha():
        return src.composite_color_simple(width, height, interp, 255, 8,
            0x777777, 0x999999)
    else:
        return src.scale_simple(width, height, interp)

def fit_2_in_rectangle(src1, src2, width, height, interp=None, scale_up=False):
    
    ''' Returns a 2-tuple with two pixbufs scaled from <src1> and <src2>
    to fit together (side-by-side) into a rectangle with dimensions
    <width> x <height>. A negative <width> or <height> means an
    unbounded dimension, both can not be negative.
    
    If <interp> is set it is used as the scaling method, otherwise the
    default value from preferences is used.
    
    Unless <scale_up> is True we don't stretch images smaller than the
    given rectangle.
    '''

    # "Unbounded" really means "bounded to 10000 px", for simplicity.
    # Comix would choke on larger images anyway.
    if width < 0:
        width = 10000
    elif height < 0:
        height = 10000

    total_width = src1.get_width() + src2.get_width()
    src1s_part = src1.get_width() * width / total_width
    
    src1s_max_scale = max(float(src1.get_height()) / height, 
        float(src1.get_width()) / src1s_part)
    src1s_part = int(src1s_part * (float(src1.get_width()) / src1s_part) /
        src1s_max_scale)

    src2s_part = width - src1s_part

    src2s_max_scale = max(float(src2.get_height()) / height, 
        float(src2.get_width()) / src2s_part)
    src2s_part = int(src2s_part * (float(src2.get_width()) / src2s_part) /
        src2s_max_scale)

    src1s_part = width - src2s_part

    return (fit_in_rectangle(src1, src1s_part, height, interp, scale_up),
        fit_in_rectangle(src2, src2s_part, height, interp, scale_up))

