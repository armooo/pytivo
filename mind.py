import cookielib
import urllib2
import urllib
import struct
import httplib 
import time
import warnings

try:
    import xml.etree.ElementTree as ElementTree 
except ImportError:
    try:
        import elementtree.ElementTree as ElementTree
    except ImportError:
        warnings.warn('Python 2.5 or higher or elementtree is needed to use the TivoPush')
        
if 'ElementTree' not in locals():

    class Mind:
        def __init__(self, *arg, **karg):
            raise Exception('Python 2.5 or higher or elementtree is needed to use the TivoPush')
    
else:

    class Mind:
        def __init__(self, username, password, debug=False):
            self.__username = username
            self.__password = password 

            self.__debug = debug

            self.__cj = cookielib.CookieJar()
            self.__opener = urllib2.build_opener(urllib2.HTTPSHandler(debuglevel=1), urllib2.HTTPCookieProcessor(self.__cj))

            self.__login()

            if not self.__pcBodySearch():
                self.__pcBodyStore('pyTivo', True)

        def pushVideo(self, tsn, url, description='test', duration='40000', size='3000000', title='test', subtitle='test'):
            
            # It looks like tivo only supports one pc per house
            pc_body_id = self.__pcBodySearch()[0]
            offer_id, content_id = self.__bodyOfferModify(tsn, pc_body_id, description, duration, size, title, subtitle, url)
            self.__subscribe(offer_id, content_id, tsn)

        def bodyOfferSchedule(self, pc_body_id):

            data = {'pcBodyId' : pc_body_id,}
            r = urllib2.Request(
                '/Steph%27s%20Videos/The%20Fairly%20Odd%20Parents%20-%20Channel%20Chasers.xvid-pyro.avi', 
                dictcode(data),
                {'Content-Type' : 'x-tivo/dict-binary'}
            )
            result = self.__opener.open(r)

            self.__log('bodyOfferSchedule\n%s\n\n%sg' % (data, result))

            return result.read()

        def __log(self, message):
            if self.__debug:
                print message
                print

        def __login(self):

            data = {
                'cams_security_domain' : 'tivocom',
                'cams_login_config' : 'http',
                'cams_cb_username' : self.__username,
                'cams_cb_password' : self.__password,
                'cams_original_url' : '/mind/mind7?type=infoGet'
            }

            r =  urllib2.Request(
                'https://mind.tivo.com:8181/mind/login', 
                urllib.urlencode(data)
            )
            try:
                result = self.__opener.open(r)
            except:
                pass

            self.__log('__login\n%s' % (data))

        def __bodyOfferModify(self, tsn, pc_body_id, description, duration, size, title, subtitle, url):

            data = {
                'bodyId' : 'tsn:' + tsn,
                'description' : description,
                'duration' : duration,
                'encodingType' : 'mpeg2ProgramStream',
                'partnerId' : 'tivo:pt.3187',
                'pcBodyId' : pc_body_id,
                'publishDate' : time.strftime('%Y-%m-%d %H:%M%S', time.gmtime()),
                'size' : size,
                'source' : 'file:/C%3A%2FDocuments%20and%20Settings%2FStephanie%2FDesktop%2FVideo',
                'state' : 'complete',
                'subtitle' : subtitle,
                'title' : title,
                'url' : url,
            }
            r = urllib2.Request(
                'https://mind.tivo.com:8181/mind/mind7?type=bodyOfferModify&bodyId=tsn:' + tsn, 
                dictcode(data),
                {'Content-Type' : 'x-tivo/dict-binary'}
            )
            result = self.__opener.open(r)

            xml = ElementTree.parse(result).find('.')
            
            self.__log('__bodyOfferModify\n%s\n\n%sg' % (data, ElementTree.tostring(xml)))

            if xml.findtext('state') != 'complete':
                raise Exception(ElementTree.tostring(xml))

            offer_id = xml.findtext('offerId')
            content_id = offer_id.replace('of','ct')

            return offer_id, content_id


        def __subscribe(self, offer_id, content_id, tsn):
            data =  {
                'bodyId' : 'tsn:' + tsn,
                'idSetSource' : {
                    'contentId': content_id,
                    'offerId' : offer_id,
                    'type' : 'singleOfferSource',
                },
                'title' : 'pcBodySubscription',
                'uiType' : 'cds',
            }
            
            r = urllib2.Request(
                'https://mind.tivo.com:8181/mind/mind7?type=subscribe&bodyId=tsn:' + tsn, 
                dictcode(data),
                {'Content-Type' : 'x-tivo/dict-binary'}
            )
            result = self.__opener.open(r)

            xml = ElementTree.parse(result).find('.')

            self.__log('__subscribe\n%s\n\n%sg' % (data, ElementTree.tostring(xml)))

            return xml

        def __pcBodySearch(self):

            data = {}
            r = urllib2.Request(
                'https://mind.tivo.com:8181/mind/mind7?type=pcBodySearch', 
                dictcode(data),
                {'Content-Type' : 'x-tivo/dict-binary'}
            )
            result = self.__opener.open(r)

            xml = ElementTree.parse(result).find('.')


            self.__log('__pcBodySearch\n%s\n\n%sg' % (data, ElementTree.tostring(xml)))

            return [id.text for id in xml.findall('pcBody/pcBodyId')]

        def __collectionIdSearch(self, url):

            data = {'url' : url}
            r = urllib2.Request(
                'https://mind.tivo.com:8181/mind/mind7?type=collectionIdSearch', 
                dictcode(data),
                {'Content-Type' : 'x-tivo/dict-binary'}
            )
            result = self.__opener.open(r)

            xml = ElementTree.parse( result ).find('.')
            collection_id = xml.findtext('collectionId')

            self.__log('__collectionIdSearch\n%s\n\n%sg' % (data, ElementTree.tostring(xml)))

            return collection_id

        def __pcBodyStore(self, name, replace=False):
           
            data = {
                'name' : name,
                'replaceExisting' : str(replace).lower(),
            }

            r = urllib2.Request(
                'https://mind.tivo.com:8181/mind/mind7?type=pcBodyStore', 
                dictcode(data), 
                {'Content-Type' : 'x-tivo/dict-binary'}
            )
            result = self.__opener.open(r)

            xml = ElementTree.parse(result).find('.')

            self.__log('__pcBodySearch\n%s\n\n%s' % (data, ElementTree.tostring(xml)))

            return xml


    def dictcode(d):
        """Helper to create x-tivo/dict-binary"""
        output = []

        keys = [str(k) for k in d]
        keys.sort()

        for k in keys:
            v = d[k]

            l = len(k) | 128
            output.append( struct.pack('>B', l) )
            output.append( k )

            if isinstance(v, dict):
                output.append( struct.pack('>B', 0x02) )
                output.append( dictcode(v) )

            else:
                v = str(v)
                output.append( struct.pack('>B', 0x01) )
                l = len(v) | 128
                output.append( struct.pack('>B', l) )
                output.append( v )

            output.append( struct.pack('>B', 0x00) )

        output.append( struct.pack('>B', 0x80) )

        return ''.join(output)


if __name__ == '__main__':
        username = 'armooo@armooo.net'
        password = 'in(into)'
        tsn = '6520001802C0F2A'
        url = 'http://10.0.1.52:9032/Steph%27s%20Videos/Weekend%20%28Godard%201967%29.avi'

        mind = Mind(username, password, True)
        mind.pushVideo(tsn, url)

