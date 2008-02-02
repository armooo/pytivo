import time, os, BaseHTTPServer, SocketServer, socket, re
from urllib import unquote_plus, quote, unquote
from urlparse import urlparse
from cgi import parse_qs
from Cheetah.Template import Template
from plugin import GetPlugin
from xml.sax.saxutils import escape

SCRIPTDIR = os.path.dirname(__file__)

class TivoHTTPServer(SocketServer.ThreadingMixIn, BaseHTTPServer.HTTPServer):
    containers = {}

    def __init__(self, server_address, RequestHandlerClass):
        BaseHTTPServer.HTTPServer.__init__(self, server_address,
                                           RequestHandlerClass)
        self.daemon_threads = True

    def add_container(self, name, settings):
        if self.containers.has_key(name) or name == 'TiVoConnect':
            raise "Container Name in use"
        settings['content_type'] = GetPlugin(settings['type']).CONTENT_TYPE
        self.containers[name] = settings

class TivoHTTPHandler(BaseHTTPServer.BaseHTTPRequestHandler):

    def address_string(self):
        host, port = self.client_address[:2]
        return host

    def do_GET(self):

        basepath = unquote_plus(self.path).split('/')[1]

        ## Get File
        for name, container in self.server.containers.items():
            if basepath == name:
                plugin = GetPlugin(container['type'])
                plugin.send_file(self, container, name)
                return

        ## Not a file not a TiVo command fuck them
        if not self.path.startswith('/TiVoConnect'):
            self.infopage()
            return

        o = urlparse("http://fake.host" + self.path)
        query = parse_qs(o[4])

        mname = False
        if query.has_key('Command') and len(query['Command']) >= 1:

            command = query['Command'][0]

            # If we are looking at the root container
            if command == "QueryContainer" and \
               (not query.has_key('Container') or query['Container'][0] == '/'):
                self.root_container()
                return 

            if query.has_key('Container'):
                # Dispatch to the container plugin
                for name, container in self.server.containers.items():
                    if query['Container'][0].startswith(name):
                        plugin = GetPlugin(container['type'])
                        if hasattr(plugin,command):
                            method = getattr(plugin, command)
                            method(self, query)
                        else:
                            self.unsupported(query)
                        break
        else:
            self.unsupported(query)

    def root_container(self):
         t = Template(file=os.path.join(SCRIPTDIR, 'templates',
                                        'root_container.tmpl'))
         t.containers = self.server.containers
         t.hostname = socket.gethostname()
         t.escape = escape
         self.send_response(200)
         self.end_headers()
         self.wfile.write(t)

    def infopage(self):
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR, 'templates',
                                       'info_page.tmpl'))
        self.wfile.write(t)
        self.end_headers()

    def unsupported(self, query):
        self.send_response(404)
        self.send_header('Content-type', 'text/html')
        self.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR, 'templates',
                                       'unsupported.tmpl'))
        t.query = query
        self.wfile.write(t)

if __name__ == '__main__':
    def start_server():
        httpd = TivoHTTPServer(('', 9032), TivoHTTPHandler)
        httpd.add_container('test', 'x-container/tivo-videos',
                            r'C:\Documents and Settings\Armooo\Desktop\pyTivo\test')
        httpd.serve_forever()

    start_server()
