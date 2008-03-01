import subprocess, shutil, os, re, sys, ConfigParser, time, lrucache
import config
from debug import debug_write, fn_attr

info_cache = lrucache.LRUCache(1000)

BUFF_SIZE = config.getBuffSize()
FFMPEG = config.get('Server', 'ffmpeg')
videotest = os.path.join(os.path.dirname(__file__), 'videotest.mpg')

# XXX BIG HACK
# subprocess is broken for me on windows so super hack
def patchSubprocess():
    o = subprocess.Popen._make_inheritable

    def _make_inheritable(self, handle):
        if not handle: return subprocess.GetCurrentProcess()
        return o(self, handle)

    subprocess.Popen._make_inheritable = _make_inheritable
mswindows = (sys.platform == "win32")
if mswindows:
    patchSubprocess()

def output_video(inFile, outFile, tsn=''):
    if tivo_compatable(inFile, tsn):
        debug_write(__name__, fn_attr(), [inFile, ' is tivo compatible'])
        f = file(inFile, 'rb')
        shutil.copyfileobj(f, outFile)
        f.close() 
    else:
        debug_write(__name__, fn_attr(), [inFile, ' is not tivo compatible'])
        transcode(inFile, outFile, tsn)

def transcode(inFile, outFile, tsn=''):

    settings = {}
    settings['audio_br'] = config.getAudioBR(tsn)
    settings['audio_codec'] = select_audiocodec(inFile, tsn)
    settings['audio_fr'] = select_audiofr(inFile)
    settings['video_br'] = config.getVideoBR(tsn)
    settings['max_video_br'] = config.getMaxVideoBR()
    settings['buff_size'] = BUFF_SIZE
    settings['aspect_ratio'] = ' '.join(select_aspect(inFile, tsn))

    cmd_string = config.getFFMPEGTemplate(tsn) % settings

    cmd = [FFMPEG, '-i', inFile] + cmd_string.split()
    print 'transcoding to tivo model '+tsn[:3]+' using ffmpeg command:'
    print cmd
    debug_write(__name__, fn_attr(), ['ffmpeg command is ', ' '.join(cmd)])
    ffmpeg = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    try:
        shutil.copyfileobj(ffmpeg.stdout, outFile)
    except:
        kill(ffmpeg.pid)

def select_audiocodec(inFile, tsn = ''):
    # Default, compatible with all TiVo's
    codec = '-acodec mp2 -ac 2'
    type, width, height, fps, millisecs, kbps, akbps, acodec, afreq =  video_info(inFile)
    if akbps == None and acodec in ('ac3', 'liba52', 'mp2'):
        cmd_string = '-y -vcodec mpeg2video -r 29.97 -b 1000k -acodec copy -t 00:00:01 -f vob -'
        if video_check(inFile, cmd_string):
            type, width, height, fps, millisecs, kbps, akbps, acodec, afreq =  video_info(videotest)
    if config.isHDtivo(tsn):
        # Is HD Tivo, use ac3
        codec = '-acodec ac3'
        if acodec in ('ac3', 'liba52') and not akbps == None and \
            int(akbps) <= config.getMaxAudioBR(tsn):
            # compatible codec and bitrate, do not reencode audio
            codec = '-acodec copy'
    if acodec == 'mp2' and not akbps == None and \
        int(akbps) <= config.getMaxAudioBR(tsn):
        # compatible codec and bitrate, do not reencode audio
        codec = '-acodec copy'
    return codec

def select_audiofr(inFile):
    freq = '-ar 48000'  #default
    type, width, height, fps, millisecs, kbps, akbps, acodec, afreq =  video_info(inFile)
    if not afreq == None and afreq in ('44100', '48000'):
        # compatible frequency
        freq = '-ar ' + afreq
    return freq

def select_aspect(inFile, tsn = ''):
    TIVO_WIDTH = config.getTivoWidth(tsn)
    TIVO_HEIGHT = config.getTivoHeight(tsn)

    type, width, height, fps, millisecs, kbps, akbps, acodec, afreq =  video_info(inFile)

    debug_write(__name__, fn_attr(), ['tsn:', tsn])

    aspect169 = config.get169Setting(tsn)

    debug_write(__name__, fn_attr(), ['aspect169:', aspect169])

    optres = config.getOptres()

    debug_write(__name__, fn_attr(), ['optres:', optres])

    if optres:
        optHeight = config.nearestTivoHeight(height)
        optWidth = config.nearestTivoWidth(width)
        if optHeight < TIVO_HEIGHT:
            TIVO_HEIGHT = optHeight
        if optWidth < TIVO_WIDTH:
            TIVO_WIDTH = optWidth

    d = gcd(height,width)
    ratio = (width*100)/height
    rheight, rwidth = height/d, width/d

    debug_write(__name__, fn_attr(), ['File=', inFile, ' Type=', type, ' width=', width, ' height=', height, ' fps=', fps, ' millisecs=', millisecs, ' ratio=', ratio, ' rheight=', rheight, ' rwidth=', rwidth, ' TIVO_HEIGHT=', TIVO_HEIGHT, 'TIVO_WIDTH=', TIVO_WIDTH])

    multiplier16by9 = (16.0 * TIVO_HEIGHT) / (9.0 * TIVO_WIDTH)
    multiplier4by3  =  (4.0 * TIVO_HEIGHT) / (3.0 * TIVO_WIDTH)
   
    if config.isHDtivo(tsn) and height <= TIVO_HEIGHT and config.getOptres() == False:
        return [] #pass all resolutions to S3/HD, except heights greater than conf height
		# else, optres is enabled and resizes SD video to the "S2" standard on S3/HD.
    elif (rwidth, rheight) in [(4, 3), (10, 11), (15, 11), (59, 54), (59, 72), (59, 36), (59, 54)]:
        debug_write(__name__, fn_attr(), ['File is within 4:3 list.'])
        return ['-aspect', '4:3', '-s', str(TIVO_WIDTH) + 'x' + str(TIVO_HEIGHT)]
    elif ((rwidth, rheight) in [(16, 9), (20, 11), (40, 33), (118, 81), (59, 27)]) and aspect169:
        debug_write(__name__, fn_attr(), ['File is within 16:9 list and 16:9 allowed.'])
        return ['-aspect', '16:9', '-s', str(TIVO_WIDTH) + 'x' + str(TIVO_HEIGHT)]
    else:
        settings = []
        #If video is wider than 4:3 add top and bottom padding
        if (ratio > 133): #Might be 16:9 file, or just need padding on top and bottom
            if aspect169 and (ratio > 135): #If file would fall in 4:3 assume it is supposed to be 4:3 
                if (ratio > 177):#too short needs padding top and bottom
                    endHeight = int(((TIVO_WIDTH*height)/width) * multiplier16by9)
                    settings.append('-aspect')
                    settings.append('16:9')
                    if endHeight % 2:
                        endHeight -= 1
                    if endHeight < TIVO_HEIGHT * 0.99:
                        settings.append('-s')
                        settings.append(str(TIVO_WIDTH) + 'x' + str(endHeight))

                        topPadding = ((TIVO_HEIGHT - endHeight)/2)
                        if topPadding % 2:
                            topPadding -= 1
                        
                        settings.append('-padtop')
                        settings.append(str(topPadding))
                        bottomPadding = (TIVO_HEIGHT - endHeight) - topPadding
                        settings.append('-padbottom')
                        settings.append(str(bottomPadding))
                    else:   #if only very small amount of padding needed, then just stretch it
                        settings.append('-s')
                        settings.append(str(TIVO_WIDTH) + 'x' + str(TIVO_HEIGHT))
                    debug_write(__name__, fn_attr(), ['16:9 aspect allowed, file is wider than 16:9 padding top and bottom', ' '.join(settings)])
                else: #too skinny needs padding on left and right.
                    endWidth = int((TIVO_HEIGHT*width)/(height*multiplier16by9))
                    settings.append('-aspect')
                    settings.append('16:9')
                    if endWidth % 2:
                        endWidth -= 1
                    if endWidth < (TIVO_WIDTH-10):
                        settings.append('-s')
                        settings.append(str(endWidth) + 'x' + str(TIVO_HEIGHT))

                        leftPadding = ((TIVO_WIDTH - endWidth)/2)
                        if leftPadding % 2:
                            leftPadding -= 1

                        settings.append('-padleft')
                        settings.append(str(leftPadding))
                        rightPadding = (TIVO_WIDTH - endWidth) - leftPadding
                        settings.append('-padright')
                        settings.append(str(rightPadding))
                    else: #if only very small amount of padding needed, then just stretch it
                        settings.append('-s')
                        settings.append(str(TIVO_WIDTH) + 'x' + str(TIVO_HEIGHT))
                    debug_write(__name__, fn_attr(), ['16:9 aspect allowed, file is narrower than 16:9 padding left and right\n', ' '.join(settings)])
            else: #this is a 4:3 file or 16:9 output not allowed
                settings.append('-aspect')
                settings.append('4:3')
                endHeight = int(((TIVO_WIDTH*height)/width) * multiplier4by3)
                if endHeight % 2:
                    endHeight -= 1
                if endHeight < TIVO_HEIGHT * 0.99:
                    settings.append('-s')
                    settings.append(str(TIVO_WIDTH) + 'x' + str(endHeight))

                    topPadding = ((TIVO_HEIGHT - endHeight)/2)
                    if topPadding % 2:
                        topPadding -= 1
                    
                    settings.append('-padtop')
                    settings.append(str(topPadding))
                    bottomPadding = (TIVO_HEIGHT - endHeight) - topPadding
                    settings.append('-padbottom')
                    settings.append(str(bottomPadding))
                else:   #if only very small amount of padding needed, then just stretch it
                    settings.append('-s')
                    settings.append(str(TIVO_WIDTH) + 'x' + str(TIVO_HEIGHT))
                debug_write(__name__, fn_attr(), ['File is wider than 4:3 padding top and bottom\n', ' '.join(settings)])

            return settings
        #If video is taller than 4:3 add left and right padding, this is rare. All of these files will always be sent in
        #an aspect ratio of 4:3 since they are so narrow.
        else:
            endWidth = int((TIVO_HEIGHT*width)/(height*multiplier4by3))
            settings.append('-aspect')
            settings.append('4:3')
            if endWidth % 2:
                endWidth -= 1
            if endWidth < (TIVO_WIDTH * 0.99):
                settings.append('-s')
                settings.append(str(endWidth) + 'x' + str(TIVO_HEIGHT))

                leftPadding = ((TIVO_WIDTH - endWidth)/2)
                if leftPadding % 2:
                    leftPadding -= 1

                settings.append('-padleft')
                settings.append(str(leftPadding))
                rightPadding = (TIVO_WIDTH - endWidth) - leftPadding
                settings.append('-padright')
                settings.append(str(rightPadding))
            else: #if only very small amount of padding needed, then just stretch it
                settings.append('-s')
                settings.append(str(TIVO_WIDTH) + 'x' + str(TIVO_HEIGHT))

            debug_write(__name__, fn_attr(), ['File is taller than 4:3 padding left and right\n', ' '.join(settings)])
            
            return settings

def tivo_compatable(inFile, tsn = ''):
    supportedModes = [[720, 480], [704, 480], [544, 480], [480, 480], [352, 480]]
    type, width, height, fps, millisecs, kbps, akbps, acodec, afreq =  video_info(inFile)
    #print type, width, height, fps, millisecs, kbps, akbps, acodec

    if (inFile[-5:]).lower() == '.tivo':
        debug_write(__name__, fn_attr(), ['True, ends with .tivo', inFile])
        return True

    if not type == 'mpeg2video':
        #print 'Not Tivo Codec'
        debug_write(__name__, fn_attr(), ['False, type', type, 'not mpeg2video', inFile])
        return False

    if (inFile[-3:]).lower() == '.ts':
        debug_write(__name__, fn_attr(), ['False, transport stream not supported', inFile])
        return False

    if not akbps or int(akbps) > config.getMaxAudioBR(tsn):
        debug_write(__name__, fn_attr(), ['False,', akbps, 'kbps exceeds max audio bitrate', inFile])
        return False

    if not kbps or int(kbps)-int(akbps) > config.strtod(config.getMaxVideoBR())/1000:
        debug_write(__name__, fn_attr(), ['False,', kbps, 'kbps exceeds max video bitrate', inFile])
        return False

    if config.isHDtivo(tsn):
        debug_write(__name__, fn_attr(), ['True, , HD Tivo detected', inFile])
        return True

    if not fps == '29.97':
        #print 'Not Tivo fps'
        debug_write(__name__, fn_attr(), ['False, ', fps, 'fps, should be 29.97', inFile])
        return False

    for mode in supportedModes:
        if (mode[0], mode[1]) == (width, height):
            #print 'Is TiVo!'
            debug_write(__name__, fn_attr(), ['True, ', width, 'x', height, 'is valid', inFile])
            return True
        #print 'Not Tivo dimensions'
    return False

def video_info(inFile):
    mtime = os.stat(inFile).st_mtime
    if inFile != videotest:
        if inFile in info_cache and info_cache[inFile][0] == mtime:
            debug_write(__name__, fn_attr(), [inFile, ' cache hit!'])
            return info_cache[inFile][1]

    if (inFile[-5:]).lower() == '.tivo':
        info_cache[inFile] = (mtime, (True, True, True, True, True, True, True, True, True))
        debug_write(__name__, fn_attr(), [inFile, ' ends in .tivo.'])
        return True, True, True, True, True, True, True, True, True

    cmd = [FFMPEG, '-i', inFile ] 
    ffmpeg = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, stdin=subprocess.PIPE)

    # wait 10 sec if ffmpeg is not back give up
    for i in xrange(200):
        time.sleep(.05)
        if not ffmpeg.poll() == None:
            break
    
    if ffmpeg.poll() == None:
        kill(ffmpeg.pid)
        info_cache[inFile] = (mtime, (None, None, None, None, None, None, None, None, None))
        return None, None, None, None, None, None, None, None, None

    output = ffmpeg.stderr.read()
    debug_write(__name__, fn_attr(), ['ffmpeg output=', output])

    rezre = re.compile(r'.*Video: ([^,]+),.*')
    x = rezre.search(output)
    if x:
        codec = x.group(1)
    else:
        info_cache[inFile] = (mtime, (None, None, None, None, None, None, None, None, None))
        debug_write(__name__, fn_attr(), ['failed at codec'])
        return None, None, None, None, None, None, None, None, None

    rezre = re.compile(r'.*Video: .+, (\d+)x(\d+)[, ].*')
    x = rezre.search(output)
    if x:
        width = int(x.group(1))
        height = int(x.group(2))
    else:
        info_cache[inFile] = (mtime, (None, None, None, None, None, None, None, None, None))
        debug_write(__name__, fn_attr(), ['failed at width/height'])
        return None, None, None, None, None, None, None, None, None

    rezre = re.compile(r'.*Video: .+, (.+) (?:fps|tb).*')
    x = rezre.search(output)
    if x:
        fps = x.group(1)
    else:
        info_cache[inFile] = (mtime, (None, None, None, None, None, None, None, None, None))
        debug_write(__name__, fn_attr(), ['failed at fps'])
        return None, None, None, None, None, None, None, None, None

    # Allow override only if it is mpeg2 and frame rate was doubled to 59.94
    if (not fps == '29.97') and (codec == 'mpeg2video'):
        # First look for the build 7215 version
        rezre = re.compile(r'.*film source: 29.97.*')
        x = rezre.search(output.lower() )
        if x:
            debug_write(__name__, fn_attr(), ['film source: 29.97 setting fps to 29.97'])
            fps = '29.97'
        else:
            # for build 8047:
            rezre = re.compile(r'.*frame rate differs from container frame rate: 29.97.*')
            debug_write(__name__, fn_attr(), ['Bug in VideoReDo'])
            x = rezre.search(output.lower() )
            if x:
                fps = '29.97'

    durre = re.compile(r'.*Duration: (.{2}):(.{2}):(.{2})\.(.),')
    d = durre.search(output)
    if d:
        millisecs = ((int(d.group(1))*3600) + (int(d.group(2))*60) + int(d.group(3)))*1000 + (int(d.group(4))*100)
    else:
        millisecs = 0

    #get bitrate of source for tivo compatibility test.
    rezre = re.compile(r'.*bitrate: (.+) (?:kb/s).*')
    x = rezre.search(output)
    if x:
        kbps = x.group(1)
    else:
        kbps = None
        debug_write(__name__, fn_attr(), ['failed at kbps'])

    #get audio bitrate of source for tivo compatibility test.
    rezre = re.compile(r'.*Audio: .+, (.+) (?:kb/s).*')
    x = rezre.search(output)
    if x:
        akbps = x.group(1)
    else:
        akbps = None
        debug_write(__name__, fn_attr(), ['failed at akbps'])

    #get audio codec of source for tivo compatibility test.
    rezre = re.compile(r'.*Audio: ([^,]+),.*')
    x = rezre.search(output)
    if x:
        acodec = x.group(1)
    else:
        acodec = None
        debug_write(__name__, fn_attr(), ['failed at acodec'])

    #get audio frequency of source for tivo compatibility test.
    rezre = re.compile(r'.*Audio: .+, (.+) (?:Hz).*')
    x = rezre.search(output)
    if x:
        afreq = x.group(1)
    else:
        afreq = None
        debug_write(__name__, fn_attr(), ['failed at afreq'])

    info_cache[inFile] = (mtime, (codec, width, height, fps, millisecs, kbps, akbps, acodec, afreq))
    debug_write(__name__, fn_attr(), ['Codec=', codec, ' width=', width, ' height=', height, ' fps=', fps, ' millisecs=', millisecs, ' kbps=', kbps, ' akbps=', akbps, ' acodec=', acodec, ' afreq=', afreq])
    return codec, width, height, fps, millisecs, kbps, akbps, acodec, afreq

def video_check(inFile, cmd_string):
    cmd = [FFMPEG, '-i', inFile] + cmd_string.split()
    ffmpeg = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    try:
        shutil.copyfileobj(ffmpeg.stdout, open(videotest, 'wb'))
        return True
    except:
        kill(ffmpeg.pid)
        return False

def supported_format(inFile):
    if video_info(inFile)[0]:
        return True
    else:
        debug_write(__name__, fn_attr(), [inFile, ' is not supported'])
        return False

def kill(pid):
    debug_write(__name__, fn_attr(), ['killing pid=', str(pid)])
    if mswindows:
        win32kill(pid)
    else:
        import os, signal
        os.kill(pid, signal.SIGTERM)

def win32kill(pid):
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(1, False, pid)
        ctypes.windll.kernel32.TerminateProcess(handle, -1)
        ctypes.windll.kernel32.CloseHandle(handle)

def gcd(a,b):
    while b:
        a, b = b, a % b
    return a

