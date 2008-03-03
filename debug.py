import ConfigParser, os, re, sys
import config
p = os.path.dirname(__file__)

def debug_write(srcMod, fnAttr, data):
    if config.getDebug():
        debug_out = []
        modname=srcMod.split('.')[-1]
        debug_out.append(modname+'.'+fnAttr[1]+' ['+fnAttr[0]+'] ')
        for x in data:
            debug_out.append(str(x))
        fdebug = open('debug.txt', 'a')
        fdebug.write(' '.join(debug_out)+'\n')
        print '___'+' '.join(debug_out)
        fdebug.close()

def fn_attr():
    "returns name of calling function and line number"
    return sys._getframe(1).f_code.co_name, str(sys._getframe(1).f_lineno)

def print_conf(srcMod, fnAttr):
    if config.getDebug():
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
