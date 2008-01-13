# Photo module for pyTivo by William McBrine <wmcbrine@users.sf.net>
# based partly on music.py and plugin.py
#
# After version 0.15, see git for the history
#
# Version 0.15, Dec. 29 -- allow Unicode; better error messages
# Version 0.14, Dec. 26 -- fix Random sort; handle ItemCount == 0
# Version 0.13, Dec. 19 -- more thread-safe; use draft mode always
# Version 0.12, Dec. 18 -- get date and orientation from Exif
# Version 0.11, Dec. 16 -- handle ItemCount, AnchorItem etc. correctly
# Version 0.10, Dec. 14 -- give full list if no ItemCount; use antialias
#                          mode always; allow larger thumbnails
# Version 0.9,  Dec. 13 -- different sort types
# Version 0.8,  Dec. 12 -- faster thumbnails, better quality full views
# Version 0.7,  Dec. 11 -- fix missing item on thumbnail scroll up, 
#                          better anchor and path handling
# Version 0.6,  Dec. 10 -- cache recursive lookups for faster slide shows
# Version 0.5,  Dec. 10 -- fix reboot problem by keeping directory names
#                          (vs. contents) out of "Recurse=Yes" lists
# Version 0.4,  Dec. 10 -- drop the use of playable_cache, add path
#                          separator kludges for Windows
# Version 0.3,  Dec. 8  -- revert to using PixelShape, workaround for 
#                          Image.save() under Windows
# Version 0.2,  Dec. 8  -- thumbnail caching, faster thumbnails
# Version 0.1,  Dec. 7, 2007

import os, re, random, urllib, threading, time, cgi
import Image
from cStringIO import StringIO
from Cheetah.Template import Template
from Cheetah.Filters import Filter
from plugin import Plugin
from xml.sax.saxutils import escape
from lrucache import LRUCache

SCRIPTDIR = os.path.dirname(__file__)

CLASS_NAME = 'Photo'

if os.path.sep == '/':
    quote = urllib.quote
    unquote = urllib.unquote_plus
else:
    quote = lambda x: urllib.quote(x.replace(os.path.sep, '/'))
    unquote = lambda x: urllib.unquote_plus(x).replace('/', os.path.sep)

# Match Exif date -- YYYY:MM:DD HH:MM:SS
exif_date = re.compile(r'(\d{4}):(\d\d):(\d\d) (\d\d):(\d\d):(\d\d)').search

# Match Exif orientation, Intel and Motorola versions
exif_orient_i = \
    re.compile('\x12\x01\x03\x00\x01\x00\x00\x00(.)\x00\x00\x00').search
exif_orient_m = \
    re.compile('\x01\x12\x00\x03\x00\x00\x00\x01\x00(.)\x00\x00').search

# Preload the template
tname = os.path.join(SCRIPTDIR, 'templates', 'container.tmpl')
photo_template = file(tname, 'rb').read()

class EncodeUnicode(Filter):
    def filter(self, val, **kw):
        """Encode Unicode strings, by default in UTF-8"""

        if kw.has_key('encoding'):
            encoding = kw['encoding']
        else:
            encoding='utf8'
                            
        if type(val) == type(u''):
            filtered = val.encode(encoding)
        else:
            filtered = str(val)
        return filtered

class Photo(Plugin):
    
    CONTENT_TYPE = 'x-container/tivo-photos'

    class LockedLRUCache(LRUCache):
        def __init__(self, num):
            LRUCache.__init__(self, num)
            self.lock = threading.RLock()

        def acquire(self, blocking=1):
            return self.lock.acquire(blocking)

        def release(self):
            self.lock.release()

        def __setitem__(self, key, obj):
            self.acquire()
            LRUCache.__setitem__(self, key, obj)
            self.release()

    media_data_cache = LockedLRUCache(300)  # info and thumbnails
    recurse_cache = LockedLRUCache(5)       # recursive directory lists
    dir_cache = LockedLRUCache(10)          # non-recursive lists

    def send_file(self, handler, container, name):

        def send_jpeg(data):
            handler.send_response(200)
            handler.send_header('Content-Type', 'image/jpeg')
            handler.send_header('Content-Length', len(data))
            handler.send_header('Connection', 'close')
            handler.end_headers()
            handler.wfile.write(data)

        path, query = handler.path.split('?')
        infile = os.path.join(os.path.normpath(container['path']),
                              unquote(path)[len(name) + 2:])
        opts = cgi.parse_qs(query)

        if 'Format' in opts and opts['Format'][0] != 'image/jpeg':
            handler.send_error(415)
            return

        try:
            attrs = self.media_data_cache[infile]
        except:
            attrs = None

        # Set rotation
        if attrs:
            rot = attrs['rotation']
        else:
            rot = 0

        if 'Rotation' in opts:
            rot = (rot - int(opts['Rotation'][0])) % 360
            if attrs:
                attrs['rotation'] = rot
                if 'thumb' in attrs:
                    del attrs['thumb']

        # Requested size
        width = int(opts.get('Width', ['0'])[0])
        height = int(opts.get('Height', ['0'])[0])

        # Return saved thumbnail?
        if attrs and 'thumb' in attrs and 0 < width < 100 and 0 < height < 100:
            send_jpeg(attrs['thumb'])
            return

        # Load
        try:
            pic = Image.open(unicode(infile, 'utf-8'))
        except Exception, msg:
            print 'Could not open', infile, '--', msg
            handler.send_error(404)
            return

        # Set draft mode
        try:
            pic.draft('RGB', (width, height))
        except Exception, msg:
            print 'Failed to set draft mode for', infile, '--', msg
            handler.send_error(404)
            return

        # Read Exif data if possible
        if 'exif' in pic.info:
            exif = pic.info['exif']

            # Capture date
            if attrs and not 'odate' in attrs:
                date = exif_date(exif)
                if date:
                    year, month, day, hour, minute, second = \
                        (int(x) for x in date.groups())
                    if year:
                        odate = time.mktime((year, month, day, hour,
                                             minute, second, -1, -1, -1))
                        attrs['odate'] = '%#x' % int(odate)

            # Orientation
            if attrs and 'exifrot' in attrs:
                rot = (rot + attrs['exifrot']) % 360
            else:
                if exif[6] == 'I':
                    orient = exif_orient_i(exif)
                else:
                    orient = exif_orient_m(exif)

                if orient:
                    exifrot = ((ord(orient.group(1)) - 1) * -90) % 360
                    rot = (rot + exifrot) % 360
                    if attrs:
                        attrs['exifrot'] = exifrot

        # Rotate
        try:
            if rot:
                pic = pic.rotate(rot)
        except Exception, msg:
            print 'Rotate failed on', infile, '--', msg
            handler.send_error(404)
            return

        # De-palletize
        try:
            if pic.mode == 'P':
                pic = pic.convert()
        except Exception, msg:
            print 'Palette conversion failed on', infile, '--', msg
            handler.send_error(404)
            return

        # Old size
        oldw, oldh = pic.size

        if not width: width = oldw
        if not height: width = oldh

        # Correct aspect ratio
        if 'PixelShape' in opts:
            pixw, pixh = opts['PixelShape'][0].split(':')
            oldw *= int(pixh)
            oldh *= int(pixw)

        # Resize
        ratio = float(oldw) / oldh

        if float(width) / height < ratio:
            height = int(width / ratio)
        else:
            width = int(height * ratio)

        try:
            pic = pic.resize((width, height), Image.ANTIALIAS)
        except Exception, msg:
            print 'Resize failed on', infile, '--', msg
            handler.send_error(404)
            return

        # Re-encode
        try:
            out = StringIO()
            pic.save(out, 'JPEG')
            encoded = out.getvalue()
            out.close()
        except Exception, msg:
            print 'Encode failed on', infile, '--', msg
            handler.send_error(404)
            return

        # Save thumbnails
        if attrs and width < 100 and height < 100:
            attrs['thumb'] = encoded

        # Send it
        send_jpeg(encoded)
        
    def QueryContainer(self, handler, query):

        # Reject a malformed request -- these attributes should only
        # appear in requests to send_file, but sometimes appear here
        badattrs = ('Rotation', 'Width', 'Height', 'PixelShape')
        for i in badattrs:
            if i in query:
                handler.send_error(404)
                return

        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        local_base_path = self.get_local_base_path(handler, query)
        if not handler.server.containers.has_key(cname) or \
           not self.get_local_path(handler, query):
            handler.send_error(404)
            return

        def ImageFileFilter(f):
            goodexts = ('.jpg', '.gif', '.png', '.bmp', '.tif', '.xbm',
                        '.xpm', '.pgm', '.pbm', '.ppm', '.pcx', '.tga',
                        '.fpx', '.ico', '.pcd', '.jpeg', '.tiff')
            return os.path.splitext(f)[1].lower() in goodexts

        def media_data(f):
            if f.name in self.media_data_cache:
                return self.media_data_cache[f.name]

            item = {}
            item['path'] = f.name
            item['part_path'] = f.name.replace(local_base_path, '', 1)
            item['name'] = os.path.split(f.name)[1]
            item['is_dir'] = f.isdir
            item['rotation'] = 0
            item['cdate'] = '%#x' % f.cdate
            item['mdate'] = '%#x' % f.mdate

            self.media_data_cache[f.name] = item
            return item

        t = Template(photo_template, filter=EncodeUnicode)
        t.name = subcname
        t.container = cname
        t.files, t.total, t.start = self.get_files(handler, query,
            ImageFileFilter)
        t.files = map(media_data, t.files)
        t.quote = quote
        t.escape = escape
        page = str(t)

        handler.send_response(200)
        handler.send_header('Content-Type', 'text/xml')
        handler.send_header('Content-Length', len(page))
        handler.send_header('Connection', 'close')
        handler.end_headers()
        handler.wfile.write(page)

    def get_files(self, handler, query, filterFunction):

        class FileData:
            def __init__(self, name, isdir):
                self.name = name
                self.isdir = isdir
                st = os.stat(name)
                self.cdate = int(st.st_ctime)
                self.mdate = int(st.st_mtime)

        class SortList:
            def __init__(self, files):
                self.files = files
                self.unsorted = True
                self.sortby = None
                self.last_start = 0
                self.lock = threading.RLock()

            def acquire(self, blocking=1):
                return self.lock.acquire(blocking)

            def release(self):
                self.lock.release()

        def build_recursive_list(path, recurse=True):
            files = []
            path = unicode(path, 'utf-8')
            for f in os.listdir(path):
                f = os.path.join(path, f)
                isdir = os.path.isdir(f)
                f = f.encode('utf-8')
                if recurse and isdir:
                    files.extend(build_recursive_list(f))
                else:
                   if isdir or filterFunction(f):
                       files.append(FileData(f, isdir))

            return files

        def name_sort(x, y):
            return cmp(x.name, y.name)

        def cdate_sort(x, y):
            return cmp(x.cdate, y.cdate)

        def mdate_sort(x, y):
            return cmp(x.mdate, y.mdate)

        def dir_sort(x, y):
            if x.isdir == y.isdir:
                return sortfunc(x, y)
            else:
                return y.isdir - x.isdir

        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        path = self.get_local_path(handler, query)

        # Build the list
        recurse = query.get('Recurse', ['No'])[0] == 'Yes'

        if recurse and path in self.recurse_cache:
            filelist = self.recurse_cache[path]
        elif not recurse and path in self.dir_cache:
            filelist = self.dir_cache[path]
        else:
            filelist = SortList(build_recursive_list(path, recurse))

            if recurse:
                self.recurse_cache[path] = filelist
            else:
                self.dir_cache[path] = filelist

        filelist.acquire()

        # Sort it
        seed = ''
        start = ''
        sortby = query.get('SortOrder', ['Normal'])[0] 
        if 'Random' in sortby:
            if 'RandomSeed' in query:
                seed = query['RandomSeed'][0]
                sortby += seed
            if 'RandomStart' in query:
                start = query['RandomStart'][0]
                sortby += start

        if filelist.unsorted or filelist.sortby != sortby:
            if 'Random' in sortby:
                self.random_lock.acquire()
                if seed:
                    random.seed(seed)
                random.shuffle(filelist.files)
                self.random_lock.release()
                if start:
                    local_base_path = self.get_local_base_path(handler, query)
                    start = unquote(start)
                    start = start.replace(os.path.sep + cname,
                                          local_base_path, 1)
                    filenames = [x.name for x in filelist.files]
                    try:
                        index = filenames.index(start)
                        i = filelist.files.pop(index)
                        filelist.files.insert(0, i)
                    except ValueError:
                        print 'Start not found:', start
            else:
                if 'CaptureDate' in sortby:
                    sortfunc = cdate_sort
                elif 'LastChangeDate' in sortby:
                    sortfunc = mdate_sort
                else:
                    sortfunc = name_sort

                if 'Type' in sortby:
                    filelist.files.sort(dir_sort)
                else:
                    filelist.files.sort(sortfunc)

            filelist.sortby = sortby
            filelist.unsorted = False

        files = filelist.files[:]

        # Filter it -- this section needs work
        if 'Filter' in query:
            usedir = 'folder' in query['Filter'][0]
            useimg = 'image' in query['Filter'][0]
            if not usedir:
                files = [x for x in files if not x.isdir]
            elif usedir and not useimg:
                files = [x for x in files if x.isdir]

        files, total, start = self.item_count(handler, query, cname, files,
                                              filelist.last_start)
        filelist.last_start = start
        filelist.release()
        return files, total, start
