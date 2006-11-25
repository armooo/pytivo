import subprocess, shutil, os, re

def output_video(inFile, outFile):
    if tivo_compatable(inFile):
        f = file(inFile, 'rb')
        shutil.copyfileobj(f, outFile)
        f.close()
    else:
        transcode(inFile, outFile)

def transcode(inFile, outFile):

    cmd = "ffmpeg_mp2.exe -i \"%s\" -vcodec mpeg2video -r 29.97 -b 4096 %s -ac 2 -ab 192 -f vob -" % (inFile, select_aspect(inFile))
    print cmd
    ffmpeg = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    try:
        shutil.copyfileobj(ffmpeg.stdout, outFile)
    except:
        win32kill(ffmpeg.pid)

def select_aspect(inFile):
    type, height, width, fps =  video_info(inFile)
    print type, height, width, fps
    
    d = gcd(height,width)

    rheight, rwidth = height/d, width/d
    print height, width

    if (rheight, rwidth) == (4, 3):
        return '-aspect 4:3 -s 720x480'
    elif (rheight, rwidth) == (16, 9):
        return '-aspect 16:9 -s 720x480'
    else:
        settings = []
        settings.apppend('-aspect 16:9')
      
        endHeight = (720*width)/height
        if endHeight % 2:
            endHeight -= 1
        print endHeight

        settings.append('-s 720x' + str(endHeight))

        topPadding = ((480 - endHeight)/2)
        if topPadding % 2:
            topPadding -= 1
        
        settings.append('-padtop ' + str(topPadding))
        bottomPadding = (480 - endHeight) - topPadding
        settings.append('-padbottom ' + str(bottomPadding))
            
        return ' '.join(settings)

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
    cmd = "ffmpeg_mp2.exe -i \"%s\"" % inFile
    ffmpeg = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    output = ffmpeg.stderr.read()
    
    rezre = re.compile(r'.*Video: (.+), (\d+)x(\d+), (.+) fps.*')
    m = rezre.search(output)
    if m:
        return m.group(1), int(m.group(2)), int(m.group(3)), m.group(4)
    else:
        return None, None, None, None
        
def win32kill(pid):
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(1, False, pid)
        ctypes.windll.kernel32.TerminateProcess(handle, -1)
        ctypes.windll.kernel32.CloseHandle(handle)

def gcd(a,b):
    while b:
        a, b = b, a % b
    return a
