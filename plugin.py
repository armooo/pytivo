def GetPlugin(name):
    module_name = '.'.join(['plugins', name, name])
    module = __import__(module_name, fromlist=name)
    plugin = getattr(module, name)()
    return plugin

class Plugin:

    content_type = ''

    def SendFile():
        pass
