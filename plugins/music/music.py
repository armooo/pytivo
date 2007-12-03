import os, socket, re, sys
from Cheetah.Template import Template
from plugin import Plugin
from urllib import unquote_plus, quote, unquote
from xml.sax.saxutils import escape
from lrucache import LRUCache
import eyeD3

SCRIPTDIR = os.path.dirname(__file__)

CLASS_NAME = 'Music'

class Music(Plugin):
    
    CONTENT_TYPE = 'x-container/tivo-music'

    AUDIO = 'audio'
    DIRECTORY = 'dir'

    playable_cache = {}
    playable_cache = LRUCache(1000)
    media_data_cache = LRUCache(100)
        
    def QueryContainer(self, handler, query):
        
        subcname = query['Container'][0]
        cname = subcname.split('/')[0]
        local_base_path = self.get_local_base_path(handler, query)
         
        if not handler.server.containers.has_key(cname) or not self.get_local_path(handler, query):
            handler.send_response(404)
            handler.end_headers()
            return
        
        def AudioFileFilter(file, filter_type = None):

            if filter_type:
                filter_start = filter_type.split('/')[0]
            else:
                filter_start = filter_type

            if file not in self.playable_cache:
                if os.path.isdir(file):
                    self.playable_cache[file] = self.DIRECTORY
                    
                elif eyeD3.isMp3File(file):
                    self.playable_cache[file] = self.AUDIO
                else:
                    self.playable_cache[file] = False
            
            if filter_start == self.AUDIO:
                if self.playable_cache[file] == self.AUDIO:
                    return self.playable_cache[file]
                else:
                    return False
            else: 
                return self.playable_cache[file]


        def media_data(file):
            dict = {}
            dict['path'] = file
            dict['part_path'] = file.replace(local_base_path, '')
            dict['name'] = os.path.split(file)[1]
            dict['is_dir'] = os.path.isdir(file)

            if file in self.media_data_cache:
                return self.media_data_cache[file]
        
            if os.path.isdir(file) or not eyeD3.isMp3File(file):
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
        t.container = cname
        t.files, t.total, t.start = self.get_files(handler, query, AudioFileFilter)
        t.files = map(media_data, t.files)
        t.quote = quote
        t.escape = escape
        handler.wfile.write(t)


                
