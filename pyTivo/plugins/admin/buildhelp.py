import os

SCRIPTDIR = os.path.dirname(__file__)

##Build initial help list
help_list = {}
title = ''
settings_known = {}
multiline = ''
f = open(os.path.join(SCRIPTDIR, 'help.txt'))
try:
    for line in f:
        line = line.strip()
        if multiline != '':
            if (line.rfind('+\\')+2) == len(line):
                multiline += line[0:(len(line)-2)]
                continue
            else:
                multiline += line
                help_list[title].append(multiline)
                multiline = ''
                continue
        if line == '' or line.find('#') >= 0:
            #skip blank or commented lines
            continue
        if line.find(':') <= 0:
            title = line
            help_list[title] = []
        else:
            value = line.split(':',1)[0].strip()
            data = line.split(':',1)[1].strip()
            if value.lower() == 'available in':
                #Special Setting to create section_known array
                data = data.split(',')
                for section in data:
                    section = section.lower().strip()
                    if section not in settings_known:
                        settings_known[section] = []
                    settings_known[section].append(title)
            else:
                if (line.rfind('+\\')+2) == len(line):
                    multiline += line[0:(len(line)-2)]
                else:
                    help_list[title].append(line)
finally:
    f.close()
## Done building help list

def gethelp():
    return help_list

def getknown(section):
    return settings_known[section]
