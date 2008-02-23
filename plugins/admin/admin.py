import os, socket, re, sys, ConfigParser
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
    def Admin(self, handler, query):
        #Read config file new each time in case there was any outside edits
        config = ConfigParser.ConfigParser()
        config.read(config_file_path)
        
        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'settings.tmpl'))
        t.container = cname
        t.server_data = dict(config.items('Server'))
        t.server_known = ["port", "guid", "ffmpeg", "beacon", "hack83", "debug", \
                          "optres", "audio_br", "video_br", "max_video_br", "width",\
                          "height", "ffmpeg_prams", "bufsize"]
        t.shares_data = shares_data = [ (section, dict(config.items(section))) \
                                        for section in config.sections() \
                                        if not(section.startswith('_tivo_') \
                                        or section.startswith('Server')) and \
                                        (config.has_option(section,'type') and \
                                         config.get(section,'type').lower() != 'admin')]
        t.shares_known = ["type", "path", "auto_subshares"]
        t.tivos_data = [ (section, dict(config.items(section))) for section in config.sections() \
                         if section.startswith('_tivo_')]
        t.tivos_known = ["aspect169", "audio_br", "video_br", "width", "height", "ffmpeg_prams"]
        handler.wfile.write(t)
       
    def QueryContainer(self, handler, query):
        #Read config file new each time in case there was any outside edits
        config = ConfigParser.ConfigParser()
        config.read(config_file_path)
        
        def build_inputs(settings, data, section):
            output = ''
            for key in settings:
                try:
                    output += "<tr><td>" + key + ": </td><td><input type='text' name='" + section + "." + key + "' value='" + data[key] +"'></td></tr>"
                    del data[key]
                except:
                    output += "<tr><td>" + key + ": </td><td><input type='text' name='" + section + "." + key + "' value=''></td></tr>"
            #print remaining miscellaneous settings
            if len(data) > 0:
                output += '<tr><td colspan="2" align="center">User Defined Settings</td></tr>'
                for item in data:
                    output += "<tr><td>" + item + ": </td><td><input type='text' name='" + section + "." + item + "' value='" + data[item] +"'></td></tr>"
            output += '<tr><td colspan="2" align="center">Add a User Defined Setting to this Share</td></tr>'
            output += "<tr><td><input type='text' name='" + section + ".new__setting' value=''></td><td><input type='text' name='" + section + ".new__value' value=''></td></tr>"
            return output
            
        server_data = dict(config.items('Server'))
        server = ''
        #build an array with configuration settings to use
        settings = ["port", "guid", "ffmpeg", "beacon", "hack83", "debug", "optres", "audio_br", "video_br", "max_video_br", "width", "height", "ffmpeg_prams", "bufsize"]
        server += build_inputs(settings, server_data, 'Server')

        #Keep track of the different sections
        section_map = ''
        section_count = 1
        
        shares_data = [ (section, dict(config.items(section))) for section in config.sections() if not(section.startswith('_tivo_') or section.startswith('Server')) and (config.has_option(section,'type') and config.get(section,'type').lower() != 'admin')]
        shares =''
        for name, data in shares_data:
            shares += '<tr><td colspan="2" align="center">----------------------------------</td></tr>'
            shares += '<tr><td colspan="2" align="center">[<input type="text" id="section_' + str(section_count) + '" name="section-' + str(section_count) + '" value="' + name + '">]</td></tr>'
            #build an array with configuration settings to use
            settings = ["type", "path", "auto_subshares"]
            shares += build_inputs(settings, data, "section-" + str(section_count))
            shares += '<tr><td colspan="2" align="center">Mark this share for deletion <input type="button" value="Delete" onclick="deleteme(\'section_' + str(section_count) + '\')"></td></tr>'
            section_map += "section-" + str(section_count) + ":" + name + "/"
            section_count += 1

        tivos_data = [ (section, dict(config.items(section))) for section in config.sections() if section.startswith('_tivo_')]
        tivos =''
        for name, data in tivos_data:
            tivos += '<tr><td colspan="2" align="center">----------------------------------</td></tr>'
            tivos += '<tr><td colspan="2" align="center">[<input type="text" id="section_' + str(section_count) + '" name="section-' + str(section_count) + '" value="' + name + '">]</td></tr>'
            #build an array with configuration settings to use
            settings = ["aspect169", "audio_br", "video_br", "width", "height", "ffmpeg_prams"]
            tivos += build_inputs(settings, data, "section-" + str(section_count))
            tivos += '<tr><td colspan="2" align="center">Mark this TiVo for deletion <input type="button" value="Delete" onclick="deleteme(\'section_' + str(section_count) + '\')"></td></tr>'
            section_map += "section-" + str(section_count) + ":" + name + "/"
            section_count += 1

        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'admin.tmpl'))
        t.container = cname
        t.server = server
        t.shares = shares
        t.tivos = tivos
        t.section_map = section_map
        handler.wfile.write(t)
        config.read(config_file_path + '.dist')

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
           
        sections = query['Section_Map'][0].split('/')
        sections.pop() #last item is junk
        for section in sections:
            ID, name = section.split(':')
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
        if query['new_Share'][0] != " ":
            config.add_section(query['new_Share'][0])
            config.set(query['new_Share'][0], 'type', 'video')
        if query['new_TiVo'][0] != " ":
            config.add_section(query['new_TiVo'][0])
        f = open(config_file_path, "w")
        config.write(f)
        f.close()

        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'redirect.tmpl'))
        t.container = cname
        handler.wfile.write(t)

        
