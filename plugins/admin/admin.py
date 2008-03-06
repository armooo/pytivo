import os, socket, re, sys, ConfigParser, config, time
import urllib2
from xml.dom import minidom
from ConfigParser import NoOptionError
from Cheetah.Template import Template
from plugin import Plugin
from urllib import unquote_plus, quote, unquote
from xml.sax.saxutils import escape
from lrucache import LRUCache

SCRIPTDIR = os.path.dirname(__file__)

CLASS_NAME = 'Admin'

p = os.path.dirname(__file__)
p = p.split(os.path.sep)
p.pop()
p.pop()
p = os.path.sep.join(p)
config_file_path = os.path.join(p, 'pyTivo.conf')

class Admin(Plugin):
    CONTENT_TYPE = 'text/html'

    def Reset(self, handler, query):
        config.reset()
        handler.server.reset()
        
        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'redirect.tmpl'))
        t.container = cname
        t.text = '<h3>The pyTivo Server has been soft reset.</h3>  <br>pyTivo has reloaded the pyTivo.conf file and all changed should now be in effect.'
        handler.wfile.write(t)
    
    def Admin(self, handler, query):
        #Read config file new each time in case there was any outside edits
        config = ConfigParser.ConfigParser()
        config.read(config_file_path)

        shares_data = []
        for section in config.sections():
            if not(section.startswith('_tivo_') or section.startswith('Server')):
                if not(config.has_option(section,'type')):
                    shares_data.append((section, dict(config.items(section, raw=True))))
                elif config.get(section,'type').lower() != 'admin':
                    shares_data.append((section, dict(config.items(section, raw=True))))
        
        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'settings.tmpl'))
        t.container = cname
        t.server_data = dict(config.items('Server', raw=True))
        t.server_known = ["port", "guid", "ffmpeg", "beacon", "hack83", "debug", \
                          "optres", "audio_br", "video_br", "max_video_br", "width",\
                          "height", "ffmpeg_prams", "bufsize", "precache"]
        t.shares_data = shares_data
        t.shares_known = ["type", "path", "auto_subshares"]
        t.tivos_data = [ (section, dict(config.items(section, raw=True))) for section in config.sections() \
                         if section.startswith('_tivo_')]
        t.tivos_known = ["aspect169", "audio_br", "video_br", "width", "height", "ffmpeg_prams", "shares"]
        handler.wfile.write(t)
       
    def UpdateSettings(self, handler, query):
        config = ConfigParser.ConfigParser()
        config.read(config_file_path)
        for key in query:
            if key.startswith('Server.'):
                section, option = key.split('.')
                if option == "new__setting":
                    new_setting = query[key][0]
                    continue
                if option == "new__value":
                    new_value = query[key][0]
                    continue
                if query[key][0] == " ":
                    config.remove_option(section, option)                      
                else:
                    config.set(section, option, query[key][0])
        if not(new_setting == ' ' and new_value == ' '):
            config.set('Server', new_setting, new_value)
           
        sections = query['Section_Map'][0].split(']')
        sections.pop() #last item is junk
        for section in sections:
            ID, name = section.split('|')
            if query[ID][0] == "Delete_Me":
                config.remove_section(name)
                continue
            if query[ID][0] != name:
                config.remove_section(name)
                config.add_section(query[ID][0])
            for key in query:
                if key.startswith(ID + '.'):
                    junk, option = key.split('.')
                    if option == "new__setting":
                        new_setting = query[key][0]
                        continue
                    if option == "new__value":
                        new_value = query[key][0]
                        continue
                    if query[key][0] == " ":
                        config.remove_option(query[ID][0], option)                      
                    else:
                        config.set(query[ID][0], option, query[key][0])
            if not(new_setting == ' ' and new_value == ' '):
                config.set(query[ID][0], new_setting, new_value)
        if query['new_Section'][0] != " ":
            config.add_section(query['new_Section'][0])
        f = open(config_file_path, "w")
        config.write(f)
        f.close()

        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'redirect.tmpl'))
        t.container = cname
        t.text = '<h3>Your Settings have been saved.</h3>  <br>You settings have been saved to the pyTivo.conf file.  However you will need to do a <b>Soft Reset</b> before these changes will take effect.'
        handler.wfile.write(t)
        
    def NPL(self, handler, query):
        folder = '/NowPlaying'
        if 'Folder' in query:
            folder += '/' + str(query['Folder'][0])
        theurl = 'https://192.168.1.150/TiVoConnect?Command=QueryContainer&Container=' + folder

        password = '' #TiVo MAK

        r=urllib2.Request(theurl)
        auth_handler = urllib2.HTTPDigestAuthHandler()
        auth_handler.add_password('TiVo DVR', '192.168.1.150', 'tivo', password)
        opener = urllib2.build_opener(auth_handler)
        urllib2.install_opener(opener)

        try:
            handle = urllib2.urlopen(r)
        except IOError, e:
            print "Possibly wrong Media Access Key, or IP address for your TiVo."
            handler.send_response(404)
            handler.end_headers()
            return 
        thepage = handle.read()

        xmldoc = minidom.parseString(thepage)
        items = xmldoc.getElementsByTagName('Item')

        data = []
        for item in items:
            entry = {}
            entry['Title'] = item.getElementsByTagName("Title")[0].firstChild.data
            entry['ContentType'] = item.getElementsByTagName("ContentType")[0].firstChild.data
            if (len(item.getElementsByTagName("UniqueId")) >= 1):
                entry['UniqueId'] = item.getElementsByTagName("UniqueId")[0].firstChild.data
            if entry['ContentType'] != 'x-tivo-container/folder':
                link = item.getElementsByTagName("Links")[0]
                if (len(link.getElementsByTagName("CustomIcon")) >= 1):
                    entry['Icon'] = link.getElementsByTagName("CustomIcon")[0].getElementsByTagName("Url")[0].firstChild.data
                keys = ['SourceSize', 'Duration', 'CaptureDate', 'EpisodeTitle', 'Description', 'SourceChannel', 'SourceStation']
                for key in keys:
                    try:
                        entry[key] = item.getElementsByTagName(key)[0].firstChild.data
                    except:
                        entry[key] = ''
                entry['SourceSize'] = "%.3f GB" % float(float(entry['SourceSize'])/(1024*1024*1024))
                entry['Duration'] = str(int(entry['Duration'])/(60*60*1000)).zfill(2) + ':' \
                                    + str((int(entry['Duration'])/60*1000)%60).zfill(2) + ':' \
                                    + str((int(entry['Duration'])/1000)%60).zfill(2)
                entry['CaptureDate'] = time.strftime("%b %d, %Y <br> %H:%M:%S", time.localtime(int(entry['CaptureDate'], 16)))
                        
            data.append(entry)

        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'npl.tmpl'))
        t.container = cname
        t.data = data
        handler.wfile.write(t)
        
