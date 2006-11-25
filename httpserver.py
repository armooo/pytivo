import time, os, BaseHTTPServer, SocketServer, socket, shutil, os.path
from urllib import unquote_plus
from urlparse import urlparse
from cgi import parse_qs
from Cheetah.Template import Template
from transcode import output_video

class TivoHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    containers = {}

    def add_container(self, name, type, path):
        if self.containers.has_key(name) or name == 'TivoConnect':
            raise "Container Name in use"
        self.containers[name] = {'type' : type, 'path' : path}

class TivoHTTPHandler(BaseHTTPServer.BaseHTTPRequestHandler):
    def do_GET(self):
      
        for name, container in self.server.containers.items():
            #XXX make a regex
            if self.path.startswith('/' + name):
                self.send_static(name, container)
                return
        
        if not self.path.startswith('/TiVoConnect'):
            self.infopage()
            return
        
        o = urlparse("http://fake.host" + self.path)
        query = parse_qs(o.query)

        mname = False
        if query.has_key('Command') and len(query['Command']) >= 1:
            mname = 'do_' + query['Command'][0]
        if mname and hasattr(self, mname):
            method = getattr(self, mname)
            method(query)
        else:
            self.unsuported(query)
            
    def do_QueryContainer(self, query):
        
        if not query.has_key('Container'):
            query['Container'] = ['/']
        self.send_response(200)
        self.end_headers()
        if query['Container'][0] == '/':
            t = Template(file="templates/root_container.tmpl")
            t.containers = self.server.containers
            t.hostname = socket.gethostname()
            self.wfile.write(t)
        else:
            
            subcname = unquote_plus(query['Container'][0])
            cname = subcname.split('/')[0]
             
            if not self.server.containers.has_key(cname):
                return
            
            container = self.server.containers[cname]

            folders = subcname.split('/')
            path = container['path']
            for folder in folders[1:]:
                path = path + '/' + folder
           
            files = os.listdir(path)
            totalFiles = len(files)
            
            if query.has_key('ItemCount'):
                count = int(query['ItemCount'] [0])
                index = 0
                
                if query.has_key('AnchorItem'):
                    anchor = query['AnchorItem'] [0]
                    for i in range(len(files)):
                        file_url = '/' + subcname + '/' + files[i]
                        if file_url == anchor:
                            index = i + 1
                            break
                if query.has_key('AnchorOffset'):
                    index = index +  int(query['AnchorOffset'][0])
                files = files[index:index + count]
            
            def isdir(file):
                path = container['path'] + '/' + file
                return os.path.isdir(path)
            
            t = Template(file="templates/container.tmpl")
            t.name = subcname
            t.files = files
            t.total = totalFiles
            t.start = index
            t.isdir = isdir
            self.wfile.write(t)

    def send_static(self, name, container):

        #cheep hack 
        if self.headers.getheader('Range') and not self.headers.getheader('Range') == 'bytes=0-':
            self.send_response(404)
            self.end_headers()
            return
        
        o = urlparse("http://fake.host" + self.path)
        path = unquote_plus(o.path)
        self.send_response(200)
        self.end_headers()
        #rfile = open(container['path'] + path[len(name)+1:], 'rb')
        #shutil.copyfileobj(rfile, self.wfile)
        output_video(container['path'] + path[len(name)+1:], self.wfile)
    
    def infopage(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        t = Template(file="templates/info_page.tmpl")
        self.wfile.write(t)
        self.end_headers()

    def unsuported(self, query):
        self.send_response(404)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        t = Template(file="templates/unsuported.tmpl")
        t.query = query
        self.wfile.write(t)
       
if __name__ == '__main__':
    def start_server():
        httpd = TivoHTTPServer(('', 9032), TivoHTTPHandler)
        httpd.add_container('test', 'x-container/tivo-videos', r'C:\Documents and Settings\Armooo\Desktop\pyTivo\test')
        httpd.serve_forever()

    start_server()
