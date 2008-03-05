import ConfigParser, os, re, sys
import config
import datetime 

p = os.path.dirname(__file__)

def debug_write(srcMod, fnAttr, data):
    if config.getDebug(0).lower() == 'true':
        debug_out = []
        modname=srcMod.split('.')[-1]
        debug_out.append(modname+'.'+fnAttr[1]+' ['+fnAttr[0]+'] ')
        for x in data:
            debug_out.append(str(x))
        fpath = p
        fname = []
        fname.append('debug')
        if not config.getDebug(1) == '' or not config.getDebug(2) == '':
            if os.path.isdir(config.getDebug(1)):
                fpath = config.getDebug(1)
            fname.append(os.path.split(os.path.dirname(__file__))[-1])
            if config.getDebug(2).lower() == 'split': 
                fname.append(modname)
        fname.append('txt')
        fdebug = open(os.path.join(fpath, '.'.join(fname)), 'a')
        fdebug.write(' '.join(debug_out)+'\n')
        print '___'+' '.join(debug_out)
        fdebug.close()

def fn_attr():
    "returns name of calling function and line number"
    return sys._getframe(1).f_code.co_name, str(sys._getframe(1).f_lineno)

def print_conf(srcMod, fnAttr):
    if config.getDebug(0).lower() == 'true':
        debug_write(srcMod, fnAttr, ['********************************************************']) 
        debug_write(srcMod, fnAttr, ['**  Begin pyTivo Session:', datetime.datetime.today(), ' **']) 
        debug_write(srcMod, fnAttr, ['********************************************************']) 
        debug_write(srcMod, fnAttr, ['----- begin pyTivo.conf -----'])
        conf = open(os.path.join(p, 'pyTivo.conf'))
        for line in conf.readlines():
            if line.strip().startswith('#'):
                continue
            if len(line.strip()) != 0:
                debug_write(srcMod, fnAttr, [line.strip()])
        conf.close()
        debug_write(srcMod, fnAttr, ['------- end pyTivo.conf -----'])

print_conf(__name__, fn_attr())
