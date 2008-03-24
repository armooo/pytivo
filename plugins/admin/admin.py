import os, socket, re, sys, ConfigParser, config, time
import urllib2, cookielib, thread
from xml.dom import minidom
from ConfigParser import NoOptionError
from Cheetah.Template import Template
from plugin import Plugin
from urllib import unquote_plus, quote, unquote
from urlparse import urlparse
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

status = {} #Global variable to control download threads
tivo_cache = {} #Cache of TiVo NPL

class Admin(Plugin):
    CONTENT_TYPE = 'text/html'

    def Reset(self, handler, query):
        config.reset()
        handler.server.reset()
        if 'last_page' in query:
            last_page = query['last_page'][0]
        else:
            last_page = 'Admin'
        
        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'redirect.tmpl'))
        t.container = cname
        t.time = '3'
        t.url = '/TiVoConnect?Command='+ last_page +'&Container=' + cname
        t.text = '<h3>The pyTivo Server has been soft reset.</h3>  <br>pyTivo has reloaded the pyTivo.conf'+\
                 'file and all changed should now be in effect. <br> The'+ \
                 '<a href="/TiVoConnect?Command='+ last_page +'&Container='+ cname +'"> previous</a> page will reload in 3 seconds.'
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
                          "precache", "optres", "par", "video_fps", "video_br", \
                          "max_video_br", "bufsize", "width", "height", "audio_br", \
                          "max_audio_br", "audio_fr", "audio_ch", "audio_codec", \
                          "ffmpeg_pram", "ffmpeg_tmpl"]
        t.shares_data = shares_data
        t.shares_known = ["type", "path", "auto_subshares"]
        t.tivos_data = [ (section, dict(config.items(section, raw=True))) for section in config.sections() \
                         if section.startswith('_tivo_')]
        t.tivos_known = ["aspect169", "optres", "video_fps", "video_br", "width",\
                         "height", "audio_br", "max_audio_br", "audio_fr", "audio_ch",\
                         "audio_codec", "ffmpeg_pram", "shares", "ffmpeg_tmpl"]
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
        t.time = '10'
        t.url = '/TiVoConnect?Command=Admin&Container=' + cname
        t.text = '<h3>Your Settings have been saved.</h3>  <br>You settings have been saved to the pyTivo.conf file.'+\
                 'However you will need to do a <b>Soft Reset</b> before these changes will take effect.'+\
                 '<br> The <a href="/TiVoConnect?Command=Admin&Container='+ cname +'"> Admin</a> page will reload in 10 seconds.'
        handler.wfile.write(t)
        
    def NPL(self, handler, query):
        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        folder = ''
        for name, data in config.getShares():
            if cname == name:
                if 'tivo_mak' in data:
                    tivo_mak = data['tivo_mak']
                else:
                    tivo_mak = ""
                if 'togo_path' in data:
                    togo_path = data['togo_path']
                else:
                    togo_path = ""

        if 'TiVo' in query:
            tivoIP = query['TiVo'][0]
            theurl = 'https://'+ tivoIP +'/TiVoConnect?Command=QueryContainer&Container=/NowPlaying'
            if 'Folder' in query:
                folder += str(query['Folder'][0])
                theurl += '/' + folder

            password = tivo_mak #TiVo MAK

            r=urllib2.Request(theurl)
            auth_handler = urllib2.HTTPDigestAuthHandler()
            auth_handler.add_password('TiVo DVR', tivoIP, 'tivo', password)
            opener = urllib2.build_opener(auth_handler)
            urllib2.install_opener(opener)

            if theurl in tivo_cache: #check to see if we have accessed this page before
                if tivo_cache[theurl]['thepage'] == '' or (time.time() - tivo_cache[theurl]['thepage_time']) >= 60: #if page is empty or old then retreive it
                    try:
                        handle = urllib2.urlopen(r)
                    except IOError, e:
                        handler.send_response(200)
                        handler.end_headers()
                        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'redirect.tmpl'))
                        t.container = cname
                        t.time = '20'
                        t.url = '/TiVoConnect?Command=NPL&Container=' + cname
                        t.text = '<h3>Unable to Connect to TiVo.</h3>  <br>pyTivo was unable to connect to the TiVo at ' + tivoIP +\
                                 '<br>This most likely caused by an incorrect Media Access Key.  Please return to the ToGo page and double check your Media Access Key.' +\
                                 '<br> The <a href="/TiVoConnect?Command=NPL&Container='+ cname + '"> ToGo</a> page will reload in 20 seconds.'
                        handler.wfile.write(t)
                        return 
                    tivo_cache[theurl]['thepage'] = handle.read()
                    tivo_cache[theurl]['thepage_time'] = time.time()
            else: #not in cache
                try:
                    handle = urllib2.urlopen(r)
                except IOError, e:
                    handler.send_response(200)
                    handler.end_headers()
                    t = Template(file=os.path.join(SCRIPTDIR,'templates', 'redirect.tmpl'))
                    t.container = cname
                    t.time = '20'
                    t.url = '/TiVoConnect?Command=NPL&Container=' + cname
                    t.text = '<h3>Unable to Connect to TiVo.</h3>  <br>pyTivo was unable to connect to the TiVo at ' + tivoIP +\
                             '<br>This most likely caused by an incorrect Media Access Key.  Please return to the ToGo page and double check your Media Access Key.' +\
                             '<br> The <a href="/TiVoConnect?Command=NPL&Container='+ cname + '"> ToGo</a> page will reload in 20 seconds.'
                    handler.wfile.write(t)
                    return
                tivo_cache[theurl] = {}
                tivo_cache[theurl]['thepage'] = handle.read()
                tivo_cache[theurl]['thepage_time'] = time.time()

            xmldoc = minidom.parseString(tivo_cache[theurl]['thepage'])
            items = xmldoc.getElementsByTagName('Item')

            data = []
            for item in items:
                entry = {}
                entry['Title'] = item.getElementsByTagName("Title")[0].firstChild.data
                entry['ContentType'] = item.getElementsByTagName("ContentType")[0].firstChild.data
                if (len(item.getElementsByTagName("UniqueId")) >= 1):
                    entry['UniqueId'] = item.getElementsByTagName("UniqueId")[0].firstChild.data
                if entry['ContentType'] == 'x-tivo-container/folder':
                    entry['TotalItems'] = item.getElementsByTagName("TotalItems")[0].firstChild.data
                    entry['LastChangeDate'] = item.getElementsByTagName("LastChangeDate")[0].firstChild.data
                    entry['LastChangeDate'] = time.strftime("%b %d, %Y", time.localtime(int(entry['LastChangeDate'], 16)))
                else:
                    link = item.getElementsByTagName("Links")[0]
                    if (len(link.getElementsByTagName("CustomIcon")) >= 1):
                        entry['Icon'] = link.getElementsByTagName("CustomIcon")[0].getElementsByTagName("Url")[0].firstChild.data
                    if (len(link.getElementsByTagName("Content")) >= 1):
                        entry['Url'] = link.getElementsByTagName("Content")[0].getElementsByTagName("Url")[0].firstChild.data
                        parse_url = urlparse(entry['Url'])
                        entry['Url'] = quote('http://' + parse_url[1].split(':')[0] + parse_url[2] + "?" + parse_url[4])
                    keys = ['SourceSize', 'Duration', 'CaptureDate', 'EpisodeTitle', 'Description', 'SourceChannel', 'SourceStation']
                    for key in keys:
                        try:
                            entry[key] = item.getElementsByTagName(key)[0].firstChild.data
                        except:
                            entry[key] = ''
                    entry['SourceSize'] = "%.3f GB" % float(float(entry['SourceSize'])/(1024*1024*1024))
                    entry['Duration'] = str(int(entry['Duration'])/(60*60*1000)).zfill(2) + ':' \
                                        + str((int(entry['Duration'])%(60*60*1000))/(60*1000)).zfill(2) + ':' \
                                        + str((int(entry['Duration'])/1000)%60).zfill(2)
                    entry['CaptureDate'] = time.strftime("%b %d, %Y", time.localtime(int(entry['CaptureDate'], 16)))
                            
                data.append(entry)
        else:
            data = []
            tivoIP = ''

        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'npl.tmpl'))
        t.folder = folder
        t.status = status
        t.tivo_mak = tivo_mak
        t.togo_path = togo_path
        t.tivos = handler.tivos
        t.tivoIP = tivoIP
        t.container = cname
        t.data = data
        t.unquote = unquote
        t.len = len
        handler.wfile.write(t)

    def get_tivo_file(self, url, mak, tivoIP, outfile):
        #global status
        cj = cookielib.LWPCookieJar()

        r=urllib2.Request(url)
        auth_handler = urllib2.HTTPDigestAuthHandler()
        auth_handler.add_password('TiVo DVR', tivoIP, 'tivo', mak)
        opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj), auth_handler)
        urllib2.install_opener(opener)

        try:
            handle = urllib2.urlopen(r)
        except IOError, e:
            #If we get "Too many transfers error" try a second time.  For some reason
            #urllib2 does not properly close connections when a transfer is canceled.
            if e.code == 503:
                try:
                    handle = urllib2.urlopen(r)
                except IOError, e:
                    status[url]['running'] = False
                    status[url]['error'] = e.code
                    return
            else:
                status[url]['running'] = False
                status[url]['error'] = e.code
                return

        f = open(outfile, 'wb')
        kilobytes = 0
        start_time = time.time()
        output = handle.read(1024)
        while status[url]['running'] and output != '':
            kilobytes += 1
            f.write(output)
            if ((time.time() - start_time) >= 5):
                status[url]['rate'] = int(kilobytes/(time.time() - start_time))
                kilobytes = 0
                start_time = time.time()
            output = handle.read(1024)
        status[url]['running'] = False
        handle.close()
        f.close()
        return

    def ToGo(self, handler, query):
        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        for name, data in config.getShares():
            if cname == name:
                if 'tivo_mak' in data:
                    tivo_mak = data['tivo_mak']
                else:
                    tivo_mak = ""
                if 'togo_path' in data:
                    togo_path = data['togo_path']
                else:
                    togo_path = ""
        if tivo_mak != "" and togo_path != "":
            parse_url = urlparse(str(query['Url'][0]))
            theurl = 'http://' + parse_url[1].split(':')[0] + parse_url[2] + "?" + parse_url[4]
            password = tivo_mak #TiVo MAK
            tivoIP = query['TiVo'][0]
            name = unquote(parse_url[2])[10:300].split('.')
            name.insert(-1," - " + unquote(parse_url[4]).split("id=")[1] + ".")
            outfile = os.path.join(togo_path, "".join(name))

            status[theurl] = {'running':True, 'error':'', 'rate':'', 'finished':False}

            thread.start_new_thread(Admin.get_tivo_file, (self, theurl, password, tivoIP, outfile))
            
            handler.send_response(200)
            handler.end_headers()
            t = Template(file=os.path.join(SCRIPTDIR,'templates', 'redirect.tmpl'))
            t.container = cname
            t.time = '3'
            t.url = '/TiVoConnect?Command=NPL&Container=' + cname + '&TiVo=' + query['TiVo'][0] + '&Folder=' + query['Folder'][0]
            t.text = '<h3>Transfer Initiated.</h3>  <br>You selected transfer has been initiated.'+\
                     '<br> The <a href="/TiVoConnect?Command=NPL&Container='+ cname + '&TiVo=' + query['TiVo'][0] + '&Folder=' + query['Folder'][0] +'"> ToGo</a> page will reload in 3 seconds.'
            handler.wfile.write(t)
        else:
            handler.send_response(200)
            handler.end_headers()
            t = Template(file=os.path.join(SCRIPTDIR,'templates', 'redirect.tmpl'))
            t.container = cname
            t.time = '10'
            t.url = '/TiVoConnect?Command=NPL&Container=' + cname + '&TiVo=' + query['TiVo'][0] + '&Folder=' + query['Folder'][0]
            t.text = '<h3>Missing Data.</h3>  <br>You must set both "tivo_mak" and "togo_path" before using this function.'+\
                     '<br> The <a href="/TiVoConnect?Command=NPL&Container='+ cname + '&TiVo=' + query['TiVo'][0] + '&Folder=' + query['Folder'][0] +'"> ToGo</a> page will reload in 10 seconds.'
            handler.wfile.write(t)

    def ToGoStop(self, handler, query):
        parse_url = urlparse(str(query['Url'][0]))
        theurl = 'http://' + parse_url[1].split(':')[0] + parse_url[2] + "?" + parse_url[4]
        
        status[theurl]['running'] = False
        
        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'redirect.tmpl'))
        t.container = cname
        t.time = '3'
        t.url = '/TiVoConnect?Command=NPL&Container=' + cname + '&TiVo=' + query['TiVo'][0] + '&Folder=' + query['Folder'][0]
        t.text = '<h3>Transfer Stopped.</h3>  <br>Your transfer has been stopped.'+\
                 '<br> The <a href="/TiVoConnect?Command=NPL&Container='+ cname + '&TiVo=' + query['TiVo'][0] + '&Folder=' + query['Folder'][0] +'"> ToGo</a> page will reload in 3 seconds.'
        handler.wfile.write(t)


    def SaveNPL(self, handler, query):
        config = ConfigParser.ConfigParser()
        config.read(config_file_path)
        if 'tivo_mak' in query:
            config.set(query['Container'][0], 'tivo_mak', query['tivo_mak'][0])
        if 'togo_path' in query:
            config.set(query['Container'][0], 'togo_path', query['togo_path'][0])                 
        f = open(config_file_path, "w")
        config.write(f)
        f.close()

        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'redirect.tmpl'))
        t.container = cname
        t.time = '2'
        t.url = '/TiVoConnect?last_page=NPL&Command=Reset&Container=' + cname
        t.text = '<h3>Your Settings have been saved.</h3>  <br>You settings have been saved to the pyTivo.conf file.'+\
                 'pyTivo will now do a <b>Soft Reset</b> to allow these changes to take effect.'+\
                 '<br> The <a href="/TiVoConnect?last_page=NPL&Command=Reset&Container='+ cname +'"> Reset</a> will occur in 2 seconds.'
        handler.wfile.write(t)
