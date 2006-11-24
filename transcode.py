import subprocess, shutil, os

def transcode(inFile, outFile):
    try:
        cmd = "ffmpeg_mp2.exe -y -i \"%s\" -vcodec mpeg2video -s 720x480 -r 29.97 -b 4096 -aspect 4:3 -ac 2 -ab 192 -f vob -" % inFile
        ffmpeg = subprocess.Popen(cmd, stdout=subprocess.PIPE)
        shutil.copyfileobj(ffmpeg.stdout, outFile)
    except:
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(1, False, ffmpeg.pid)
        ctypes.windll.kernel32.TerminateProcess(handle, -1)
        ctypes.windll.kernel32.CloseHandle(handle)
