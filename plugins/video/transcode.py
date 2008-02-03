import subprocess, shutil, os, re, sys, ConfigParser, time, lrucache
import config

info_cache = lrucache.LRUCache(1000)


debug = config.getDebug()
BUFF_SIZE = config.getBuffSize()

FFMPEG = config.get('Server', 'ffmpeg')

def debug_write(data):
    if debug:
        debug_out = []
        for x in data:
            debug_out.append(str(x))
        fdebug = open('debug.txt', 'a')
        fdebug.write(' '.join(debug_out))
        fdebug.close()

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
        debug_write(['output_video: ', inFile, ' is tivo compatible\n'])
        f = file(inFile, 'rb')
        shutil.copyfileobj(f, outFile)
        f.close() 
    else:
        debug_write(['output_video: ', inFile, ' is not tivo compatible\n'])
        transcode(inFile, outFile, tsn)

def transcode(inFile, outFile, tsn=''):

    settings = {}
    settings['audio_br'] = config.getAudioBR(tsn)
    settings['audio_codec'] = select_audiocodec(tsn)
    settings['video_br'] = config.getVideoBR(tsn)
    settings['max_video_br'] = config.getMaxVideoBR()
    settings['buff_size'] = BUFF_SIZE
    settings['aspect_ratio'] = ' '.join(select_aspect(inFile, tsn))

    cmd_string = config.getFFMPEGTemplate(tsn) % settings

    cmd = [FFMPEG, '-i', inFile] + cmd_string.split()
    print cmd
    debug_write(['transcode: ffmpeg command is ', ' '.join(cmd), '\n'])
    ffmpeg = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    try:
        shutil.copyfileobj(ffmpeg.stdout, outFile)
    except:
        kill(ffmpeg.pid)

def select_audiocodec(tsn = ''):
    #check for HD tivo and return compatible audio parameters
    if config.isHDtivo(tsn):
        return '-acodec ac3 -ar 48000'
    else:
        return '-acodec mp2 -ac 2 -ar 44100'

def select_aspect(inFile, tsn = ''):
    TIVO_WIDTH = config.getTivoWidth(tsn)
    TIVO_HEIGHT = config.getTivoHeight(tsn)
    
    type, width, height, fps, millisecs, kbps, akbps =  video_info(inFile)

    debug_write(['tsn:', tsn, '\n'])

    aspect169 = config.get169Setting(tsn)

    debug_write(['aspect169:', aspect169, '\n'])

    optres = config.getOptres()

    debug_write(['optres:', optres, '\n'])

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

    debug_write(['select_aspect: File=', inFile, ' Type=', type, ' width=', width, ' height=', height, ' fps=', fps, ' millisecs=', millisecs, ' ratio=', ratio, ' rheight=', rheight, ' rwidth=', rwidth, ' TIVO_HEIGHT=', TIVO_HEIGHT, 'TIVO_WIDTH=', TIVO_WIDTH, '\n'])

    multiplier16by9 = (16.0 * TIVO_HEIGHT) / (9.0 * TIVO_WIDTH)
    multiplier4by3  =  (4.0 * TIVO_HEIGHT) / (3.0 * TIVO_WIDTH)
   
    if config.isHDtivo(tsn) and height <= TIVO_HEIGHT and config.getOptres() == False:
        return [] #pass all resolutions to S3/HD, except heights greater than conf height
		# else, optres is enabled and resizes SD video to the "S2" standard on S3/HD.
    elif (rwidth, rheight) in [(4, 3), (10, 11), (15, 11), (59, 54), (59, 72), (59, 36), (59, 54)]:
        debug_write(['select_aspect: File is within 4:3 list.\n'])
        return ['-aspect', '4:3', '-s', str(TIVO_WIDTH) + 'x' + str(TIVO_HEIGHT)]
    elif ((rwidth, rheight) in [(16, 9), (20, 11), (40, 33), (118, 81), (59, 27)]) and aspect169:
        debug_write(['select_aspect: File is within 16:9 list and 16:9 allowed.\n'])
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
                    debug_write(['select_aspect: 16:9 aspect allowed, file is wider than 16:9 padding top and bottom\n', ' '.join(settings), '\n'])
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
                    debug_write(['select_aspect: 16:9 aspect allowed, file is narrower than 16:9 padding left and right\n', ' '.join(settings), '\n'])
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
                debug_write(['select_aspect: File is wider than 4:3 padding top and bottom\n', ' '.join(settings), '\n'])

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

            debug_write(['select_aspect: File is taller than 4:3 padding left and right\n', ' '.join(settings), '\n'])
            
            return settings

def tivo_compatable(inFile, tsn = ''):
    supportedModes = [[720, 480], [704, 480], [544, 480], [480, 480], [352, 480]]
    type, width, height, fps, millisecs, kbps, akbps =  video_info(inFile)
    #print type, width, height, fps, millisecs, kbps, akbps

    if (inFile[-5:]).lower() == '.tivo':
        debug_write(['tivo_compatible: ', inFile, ' ends with .tivo\n'])
        return True

    if not type == 'mpeg2video':
        #print 'Not Tivo Codec'
        debug_write(['tivo_compatible: ', inFile, ' is not mpeg2video it is ', type, '\n'])
        return False

    if (inFile[-3:]).lower() == '.ts':
        debug_write(['tivo_compatible: ', inFile, ' transport stream not supported ', '\n'])
        return False

    if not akbps or int(akbps) > config.getMaxAudioBR(tsn):
        debug_write(['tivo_compatible: ', inFile, ' max audio bitrate exceeded it is ', akbps, '\n'])
        return False

    if not kbps or int(kbps)-int(akbps) > config.strtod(config.getMaxVideoBR())/1000:
        debug_write(['tivo_compatible: ', inFile, ' max video bitrate exceeded it is ', kbps, '\n'])
        return False

    if config.isHDtivo(tsn):
        debug_write(['tivo_compatible: ', inFile, ' you have a S3 skiping the rest of the tests', '\n'])
        return True

    if not fps == '29.97':
        #print 'Not Tivo fps'
        debug_write(['tivo_compatible: ', inFile, ' is not correct fps it is ', fps, '\n'])
        return False

    for mode in supportedModes:
        if (mode[0], mode[1]) == (width, height):
            #print 'Is TiVo!'
            debug_write(['tivo_compatible: ', inFile, ' has correct width of ', width, ' and height of ', height, '\n'])
            return True
        #print 'Not Tivo dimensions'
    return False

def video_info(inFile):
    mtime = os.stat(inFile).st_mtime
    if inFile in info_cache and info_cache[inFile][0] == mtime:
        debug_write(['video_info: ', inFile, ' cache hit!', '\n'])
        return info_cache[inFile][1]

    if (inFile[-5:]).lower() == '.tivo':
        info_cache[inFile] = (mtime, (True, True, True, True, True, True, True))
        debug_write(['video_info: ', inFile, ' ends in .tivo.\n'])
        return True, True, True, True, True, True, True

    cmd = [FFMPEG, '-i', inFile ] 
    ffmpeg = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, stdin=subprocess.PIPE)

    # wait 4 sec if ffmpeg is not back give up
    for i in range(80):
        time.sleep(.05)
        if not ffmpeg.poll() == None:
            break
    
    if ffmpeg.poll() == None:
        kill(ffmpeg.pid)
        info_cache[inFile] = (mtime, (None, None, None, None, None, None, None))
        return None, None, None, None, None, None, None

    output = ffmpeg.stderr.read()
    debug_write(['video_info: ffmpeg output=', output, '\n'])

    rezre = re.compile(r'.*Video: ([^,]+),.*')
    x = rezre.search(output)
    if x:
        codec = x.group(1)
    else:
        info_cache[inFile] = (mtime, (None, None, None, None, None, None, None))
        debug_write(['video_info: failed at codec\n'])
        return None, None, None, None, None, None, None

    rezre = re.compile(r'.*Video: .+, (\d+)x(\d+)[, ].*')
    x = rezre.search(output)
    if x:
        width = int(x.group(1))
        height = int(x.group(2))
    else:
        info_cache[inFile] = (mtime, (None, None, None, None, None, None, None))
        debug_write(['video_info: failed at width/height\n'])
        return None, None, None, None, None, None, None

    rezre = re.compile(r'.*Video: .+, (.+) (?:fps|tb).*')
    x = rezre.search(output)
    if x:
        fps = x.group(1)
    else:
        info_cache[inFile] = (mtime, (None, None, None, None, None, None, None))
        debug_write(['video_info: failed at fps\n'])
        return None, None, None, None, None, None, None

    # Allow override only if it is mpeg2 and frame rate was doubled to 59.94
    if (not fps == '29.97') and (codec == 'mpeg2video'):
        # First look for the build 7215 version
        rezre = re.compile(r'.*film source: 29.97.*')
        x = rezre.search(output.lower() )
        if x:
            debug_write(['video_info: film source: 29.97 setting fps to 29.97\n'])
            fps = '29.97'
        else:
            # for build 8047:
            rezre = re.compile(r'.*frame rate differs from container frame rate: 29.97.*')
            debug_write(['video_info: Bug in VideoReDo\n'])
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
        debug_write(['video_info: failed at kbps\n'])

    #get audio bitrate of source for tivo compatibility test.
    rezre = re.compile(r'.*Audio: .+, (.+) (?:kb/s).*')
    x = rezre.search(output)
    if x:
        akbps = x.group(1)
    else:
        akbps = None
        debug_write(['video_info: failed at akbps\n'])

    info_cache[inFile] = (mtime, (codec, width, height, fps, millisecs, kbps, akbps))
    debug_write(['video_info: Codec=', codec, ' width=', width, ' height=', height, ' fps=', fps, ' millisecs=', millisecs, ' kbps=', kbps, ' akbps=', akbps, '\n'])
    return codec, width, height, fps, millisecs, kbps, akbps

def supported_format(inFile):
    if video_info(inFile)[0]:
        return True
    else:
        debug_write(['supported_format: ', inFile, ' is not supported\n'])
        return False

def kill(pid):
    debug_write(['kill: killing pid=', str(pid), '\n'])
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

