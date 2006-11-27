import subprocess, shutil, os, re, sys

SCRIPTDIR = os.path.dirname(__file__)
FFMPEG = '/usr/bin/ffmpeg'

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
        
def output_video(inFile, outFile):
    if tivo_compatable(inFile):
        f = file(inFile, 'rb')
        shutil.copyfileobj(f, outFile)
        f.close() 
    else:
        transcode(inFile, outFile)

def transcode(inFile, outFile):

    cmd = "%s -i \"%s\" -vcodec mpeg2video -r 29.97 -b 4096 %s -ac 2 -ab 192 -f vob -" % (FFMPEG, inFile, select_aspect(inFile))
    cmd = [FFMPEG, '-i', inFile, '-vcodec', 'mpeg2video', '-r', '29.97', '-b', '4096'] + select_aspect(inFile)  +  ['-ac', '2', '-ab', '192', '-f', 'vob', '-' ]   

    print cmd
 
    ffmpeg = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    try:
        shutil.copyfileobj(ffmpeg.stdout, outFile)
    except:
        win32kill(ffmpeg.pid)

def select_aspect(inFile):
    type, height, width, fps =  video_info(inFile)
    
    d = gcd(height,width)

    rheight, rwidth = height/d, width/d

    if (rheight, rwidth) in [(4, 3), (10, 11), (15, 11), (59, 54), (59, 72), (59, 36), (59, 54)]:
        return ['-aspect', '4:3', '-s', '720x480']
    elif (rheight, rwidth) in [(16, 9), (20, 11), (40, 33), (118, 81), (59, 27)]:
        return ['-aspect', '16:9', '-s', '720x480']
    else:
        settings = []
        settings.append('-aspect')
        settings.append('16:9')
      
        endHeight = (720*width)/height
        if endHeight % 2:
            endHeight -= 1

        settings.append('-s')
        settings.append('720x' + str(endHeight))

        topPadding = ((480 - endHeight)/2)
        if topPadding % 2:
            topPadding -= 1
        
        settings.append('-padtop')
        settings.append(str(topPadding))
        bottomPadding = (480 - endHeight) - topPadding
        settings.append('-padbottom')
        settings.append(str(bottomPadding))
            
        return settings

def tivo_compatable(inFile):
    suportedModes = [[720, 480], [704, 480], [544, 480], [480, 480], [352, 480]]
    type, height, width, fps =  video_info(inFile)

    if not type == 'mpeg2video':
        return False

    if not fps == '29.97':
        return False

    for mode in suportedModes:
        if (mode[0], mode[1]) == (height, width):
            return True
    return False

def video_info(inFile):
    cmd = [FFMPEG, '-i', inFile ] 
    ffmpeg = subprocess.Popen(cmd, stderr=subprocess.PIPE, stdout=subprocess.PIPE, stdin=subprocess.PIPE)
    output = ffmpeg.stderr.read()
    
    rezre = re.compile(r'.*Video: (.+), (\d+)x(\d+), (.+) fps.*')
    m = rezre.search(output)
    if m:
        return m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    else:
        return None, None, None, None
       
def suported_format(inFile):
    if video_info(inFile)[0]:
        return True
    else:
        return False

def win32kill(pid):
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(1, False, pid)
        ctypes.windll.kernel32.TerminateProcess(handle, -1)
        ctypes.windll.kernel32.CloseHandle(handle)

def gcd(a,b):
    while b:
        a, b = b, a % b
    return a
