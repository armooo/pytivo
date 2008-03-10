import os, socket, re, sys, ConfigParser, config
from ConfigParser import NoOptionError
from Cheetah.Template import Template
from plugin import Plugin
from urllib import unquote_plus, quote, unquote
from xml.sax.saxutils import escape
from lrucache import LRUCache
import debug

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
        debug.debug_write(__name__, debug.fn_attr(), ['The pyTivo Server has been soft reset.'])
        debug.print_conf(__name__, debug.fn_attr())
    
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
                          "precache", "optres", "video_fps", "video_br", "max_video_br", \
                          "bufsize", "width", "height", "audio_br", "max_audio_br", \
                          "audio_fr", "audio_ch", "audio_codec", "ffmpeg_pram"]
        t.shares_data = shares_data
        t.shares_known = ["type", "path", "auto_subshares"]
        t.tivos_data = [ (section, dict(config.items(section, raw=True))) for section in config.sections() \
                         if section.startswith('_tivo_')]
        t.tivos_known = ["aspect169", "audio_br", "video_br", "video_fps", "width",\
                         "height", "audio_br", "max_audio_br", "audio_fr", "audio_ch",\
                         "audio_codec", "ffmpeg_pram", "shares"]
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

        
