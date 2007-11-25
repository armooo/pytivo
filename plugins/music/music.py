import os, socket, re, sys
from Cheetah.Template import Template
from plugin import Plugin
from urllib import unquote_plus, quote, unquote
from xml.sax.saxutils import escape
from lrucache import LRUCache
import eyeD3

SCRIPTDIR = os.path.dirname(__file__)

class music(Plugin):
    
    content_type = 'x-container/tivo-music'
    playable_cache = {}
    playable_cache = LRUCache(1000)
    media_data_cache = LRUCache(100)
        
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

        def AudioFileFilter(file):
            full_path = os.path.join(path, file)

            if full_path in self.playable_cache:
                return self.playable_cache[full_path]
            if os.path.isdir(full_path) or eyeD3.isMp3File(full_path):
                self.playable_cache[full_path] = True
                return True
            else:
                self.playable_cache[full_path] = False
                return False 

        def media_data(file):
            dict = {}
            dict['path'] = file

            file = os.path.join(path, file)

            if file in self.media_data_cache:
                return self.media_data_cache[file]
        
            if isdir(file) or not eyeD3.isMp3File(file):
                self.media_data_cache[file] = dict
                return dict

            try:
                audioFile = eyeD3.Mp3AudioFile(file)
                dict['Duration'] = audioFile.getPlayTime() * 1000
                dict['SourceBitRate'] = audioFile.getBitRate()[1]
                dict['SourceSampleRate'] = audioFile.getSampleFreq()

                tag = audioFile.getTag()
                dict['ArtistName'] = str(tag.getArtist())
                dict['AlbumTitle'] = str(tag.getAlbum())
                dict['SongTitle'] = str(tag.getTitle())
                dict['AlbumYear'] = tag.getYear()
            
                dict['MusicGenre'] = tag.getGenre().getName()
            except:
                pass
            
            self.media_data_cache[file] = dict
            return dict
            
        handler.send_response(200)
        handler.end_headers()
        t = Template(file=os.path.join(SCRIPTDIR,'templates', 'container.tmpl'))
        t.name = subcname
        t.files, t.total, t.start = self.get_files(handler, query, AudioFileFilter)
        t.files = map(media_data, t.files)
        t.isdir = isdir
        t.quote = quote
        t.escape = escape
        handler.wfile.write(t)


                
