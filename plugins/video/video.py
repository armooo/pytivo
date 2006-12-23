import transcode, os, socket, re
from Cheetah.Template import Template
from plugin import Plugin
from urllib import unquote_plus, quote, unquote
from urlparse import urlparse
from xml.sax.saxutils import escape

SCRIPTDIR = os.path.dirname(__file__)

class video(Plugin):
    
    content_type = 'x-container/tivo-videos'

    def SendFile(self, handler, container, name):
        
        #cheep hack 
        if handler.headers.getheader('Range') and not handler.headers.getheader('Range') == 'bytes=0-':
            handler.send_response(404)
            handler.end_headers()
            return
        
        o = urlparse("http://fake.host" + handler.path)
        path = unquote_plus(o.path)
        handler.send_response(200)
        handler.end_headers()
        transcode.output_video(container['path'] + path[len(name)+1:], handler.wfile)
        
    def QueryContainer(self, handler, query):
        
        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
         
        if not handler.server.containers.has_key(cname) or not self.get_local_path(handler, query):
            handler.send_response(404)
            handler.end_headers()
            return
        
        path = self.get_local_path(handler, query)
        def isdir(file):
            return os.path.isdir(os.path.join(path, file))                     

        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'container.tmpl'))
        t.name = subcname
        t.files, t.total, t.start = self.get_files(handler, query)
        t.isdir = isdir
        t.quote = quote
        t.escape = escape
        handler.wfile.write(t)

    def get_local_path(self, handler, query):

        subcname = query['Container'][0]
        container = handler.server.containers[subcname.split('/')[0]]

        path = container['path']
        for folder in subcname.split('/')[1:]:
            if folder == '..':
                return False
            path = os.path.join(path, folder)
        return path

    def get_files(self, handler, query):
        subcname = query['Container'][0]
        path = self.get_local_path(handler, query)
        
        files = os.listdir(path)
        files = filter(lambda f: os.path.isdir(os.path.join(path, f)) or transcode.suported_format(os.path.join(path,f)), files)
        totalFiles = len(files)

        def dir_sort(x, y):
            xdir = os.path.isdir(os.path.join(path, x))
            ydir = os.path.isdir(os.path.join(path, y))

            if xdir and ydir:
                return name_sort(x, y)
            elif xdir:
                return -1
            elif ydir:
                return 1
            else:
                return name_sort(x, y)

        def name_sort(x, y):
            numbername = re.compile(r'(\d*)(.*)')
            m = numbername.match(x)
            xNumber = m.group(1)
            xStr = m.group(2)
            m = numbername.match(y)
            yNumber = m.group(1)
            yStr = m.group(2)
            
            if xNumber and yNumber:
                xNumber, yNumber = int(xNumber), int(yNumber)
                if xNumber == yNumber:
                    return cmp(xStr, yStr)
                else:
                    return cmp(xNumber, yNumber)
            elif xNumber:
                return -1
            elif yNumber:
                return 1
            else:
                return cmp(xStr, yStr)

        files.sort(dir_sort)

        index = 0
        if query.has_key('ItemCount'):
            count = int(query['ItemCount'] [0])
            
            if query.has_key('AnchorItem'):
                anchor = unquote(query['AnchorItem'][0])
                for i in range(len(files)):
                    
                    if os.path.isdir(os.path.join(path,files[i])):
                        file_url = '/TiVoConnect?Command=QueryContainer&Container=' + subcname + '/' + files[i]
                    else:                                
                        file_url = '/' + subcname + '/' + files[i]
                    if file_url == anchor:
                        index = i + 1
                        break
            if query.has_key('AnchorOffset'):
                index = index +  int(query['AnchorOffset'][0])
            files = files[index:index + count]

        return files, totalFiles, index
