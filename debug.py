import ConfigParser, os, re, sys
import config
p = os.path.dirname(__file__)

def debug_write(srcMod, fnAttr, data):
    if config.getDebug():
        debug_out = []
        debug_out.append(srcMod+'.'+fnAttr[1]+' ['+fnAttr[0]+'] ')
        for x in data:
            debug_out.append(str(x))
        fdebug = open('debug.txt', 'a')
        fdebug.write(' '.join(debug_out))
        fdebug.close()

def fn_attr():
    "returns name of calling function and line number"
    return sys._getframe(1).f_code.co_name, str(sys._getframe(1).f_lineno)

def print_conf(srcMod, fnAttr):
    if config.getDebug():
        print '----- begin pyTivo.conf -----:'
        debug_write(srcMod, fnAttr, ['----- begin pyTivo.conf -----\n'])
        conf = open(os.path.join(p, 'pyTivo.conf'))
        for line in conf.readlines():
            if line.strip().startswith('#'):
                continue
            if len(line.strip()) != 0:
                print line.strip()
                debug_write(srcMod, fnAttr, [line.strip(), '\n'])
        print '------- end pyTivo.conf -----:'
        conf.close()
        debug_write(srcMod, fnAttr, ['------- end pyTivo.conf -----\n'])
