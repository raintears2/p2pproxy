__author__="BroncoTc"
__doc__=r"""Reference to http://www.tuicool.com/articles/uMvqqeE"""
import socket
import re
import sys
import urllib2
import httplib
from shadowsocks import shell, daemon, eventloop, tcprelay, udprelay, asyncdns
from urlparse import urlparse
from xml.dom.minidom import parseString
from xml.dom.minidom import Document

socket.setdefaulttimeout(8)
# Get current router UPnP config
################################
SSDP_ADDR = "239.255.255.250"
SSDP_PORT = 1900
SSDP_MX = 2
SSDP_ST = "urn:schemas-upnp-org:device:InternetGatewayDevice:1"
ssdpRequest = "M-SEARCH * HTTP/1.1\r\n" + \
  "HOST: %s:%d\r\n" % (SSDP_ADDR, SSDP_PORT) + \
  "MAN: \"ssdp:discover\"\r\n" + \
  "MX: %d\r\n" % (SSDP_MX, ) + \
  "ST: %s\r\n" % (SSDP_ST, ) + "\r\n"
sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
sock.sendto(ssdpRequest, (SSDP_ADDR, SSDP_PORT))
try:
	resp = sock.recv(1000)
except socket.error:
	errno, errstr = sys.exc_info()[:2]
	if errno == socket.timeout:
		print "UPnP might not be supported in this network (Device discovery timeout)"
		sys.exit()
	else:
		print "Socket returned an unexpected error"
		sys.exit()
################################
parsed = re.findall(r'(?P<name>.*?): (?P<value>.*?)\r\n', resp)
location = filter(lambda x: x[0].lower() == "location", parsed) # get the location header
router_path = urlparse(location[0][1]) # use the urlparse function to create an easy to use object to hold a URL
directory = urllib2.urlopen(location[0][1]).read() # get the profile xml file and read it into a variable
dom = parseString(directory) # create a DOM object that represents the `directory` document
service_types = dom.getElementsByTagName('serviceType') # find all 'serviceType' elements
# iterate over service_types until we get either WANIPConnection
# (this should also check for WANPPPConnection, which, if I remember correctly
# exposed a similar SOAP interface on ADSL routers.
isPassable=False
for service in service_types:
	if service.childNodes[0].data.find('WANIPConnection') > 0:
		isPassable=True
		path = service.parentNode.getElementsByTagName('controlURL')[0].childNodes[0].data
if isPassable==False:
	print "Port forward is not allowed in the curent UPnP configuration"
	sys.exit()

def Get_local_ip():
	try:
		csock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
		csock.connect(('8.8.8.8', 80))
		(addr, port) = csock.getsockname()
		csock.close()
		return addr
	except socket.error:
		return "127.0.0.1"

doc = Document()
# create the envelope element and set its attributes
envelope = doc.createElementNS('', 's:Envelope')
envelope.setAttribute('xmlns:s', 'http://schemas.xmlsoap.org/soap/envelope/')
envelope.setAttribute('s:encodingStyle', 'http://schemas.xmlsoap.org/soap/encoding/')
# create the body element
body = doc.createElementNS('', 's:Body')
# create the function element and set its attribute
fn = doc.createElementNS('', 'u:AddPortMapping')
fn.setAttribute('xmlns:u', 'urn:schemas-upnp-org:service:WANIPConnection:1')
# setup the argument element names and values
# using a list of tuples to preserve order
arguments = [
  ('NewExternalPort', '23333'),		   # specify port on router
  ('NewProtocol', 'TCP'),				 # specify protocol
  ('NewInternalPort', '13579'),		   # specify port on internal host
  ('NewInternalClient', str(Get_local_ip())), # specify IP of internal host
  ('NewEnabled', '1'),					# turn mapping ON
  ('NewPortMappingDescription', 'P2Pproxy'), # add a description
  ('NewLeaseDuration', '0')]			  # how long should it be opened?
# NewEnabled should be 1 by default, but better supply it.
# NewPortMappingDescription Can be anything you want, even an empty string.
# NewLeaseDuration can be any integer BUT some UPnP devices don't support it,
# so set it to 0 for better compatibility.
argument_list = [] # container for created nodes
for k, v in arguments:
	tmp_node = doc.createElement(k)
	tmp_text_node = doc.createTextNode(v)
	tmp_node.appendChild(tmp_text_node)
	argument_list.append(tmp_node)
for arg in argument_list: # append the prepared argument nodes to the function element
	fn.appendChild(arg)
body.appendChild(fn) # append function element to the body element
envelope.appendChild(body) # append body element to envelope element
doc.appendChild(envelope) # append envelope element to document, making it the root element
pure_xml = doc.toxml() # our tree is ready, conver it to a string
conn = httplib.HTTPConnection(router_path.hostname, router_path.port) # use the object returned by urlparse.urlparse to get the hostname and port
conn.request('POST',
    path,
    pure_xml,
    {'SOAPAction': '"urn:schemas-upnp-org:service:WANIPConnection:1#AddPortMapping"',
     'Content-Type': 'text/xml'}
)
# wait for a response
resp = conn.getresponse()
if 200<>resp.status:
	print "It seems like the TCP port forwarding failed"
	sys.exit()





