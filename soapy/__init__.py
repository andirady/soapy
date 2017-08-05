import logging
import socketserver
from xml.etree import ElementTree


ElementTree.register_namespace('SOAP-ENV', "http://schemas.xmlsoap.org/soap/envelope/")
END_HEADER_TOKEN = b'\r\n\r\n' 


_soapy_services = {}
def service(action=None):
    def inner(func):
        global _soapy_services
        _soapy_services[action] = func
    return inner

def run(bind_address='', port=5000):
    logging.info(f'Serving on port {port}')
    socketserver.TCPServer.allow_reuse_address = True
    with socketserver.TCPServer((bind_address, port), SoapyHandler) as server:
        server.serve_forever()


class SoapyHandler(socketserver.BaseRequestHandler):
    def read_header(self, dat, name, default=None, cast=None):
        tok = f'\r\n{name}:'.encode('utf-8')
        i = dat.find(tok)
        if i >= 0:
            offset = i + len(tok)
            i_crlf = dat.find(b'\r\n', offset)
            if cast:
                return cast(dat[offset:i_crlf].strip())
            return dat[offset:i_crlf].strip()
        return default

    def handle(self):
        dat = self.request.recv(1024)
        soapaction = self.read_header(dat, "SOAPAction")
        contentlen = self.read_header(dat, "Content-Length", cast=int)
        trnsferenc = self.read_header(dat, "Transfer-Encoding")
        # Read until end header token.
        i_header_end = dat.find(END_HEADER_TOKEN)
        while i_header_end < 0:
            dat += self.request.recv(64)
            i_header_end = dat.find(END_HEADER_TOKEN)

        logging.info('SOAPAction: %s', soapaction)

        req_content = dat[i_header_end + len(END_HEADER_TOKEN):]
        if trnsferenc == b'chunked':
            read_sz = 10 # max chunk size of 2**64.
            chunks = []
            if len(req_content) == 0:
                req_content = self.request.recv(read_sz)

            sz, dat = req_content.split(b'\r\n', 2)
            sz = int(sz, 16)
            chunks.append(dat)
            if len(dat) < sz:
                chunks.append(self.request.recv(sz - len(dat)))
                self.request.recv(2)

            raw = b''.join(chunks)
        else:
            toread = (contentlen or 0) - len(req_content)
            if toread > 0:
                req_content += self.request.recv(toread)

        logging.debug('<-- %s', raw)
        logging.debug('-----')
        req = ElementTree.fromstring(raw)
        try:
            self.request.sendall(b'HTTP/1.1 200 OK\r\n'
                                 b'Content-Type: text/xml; charset=UTF-8\r\n'
                                 b'Transfer-Encoding: chunked\r\n'
                                 b'\r\n')

            soap_env = ElementTree.Element('{http://schemas.xmlsoap.org/soap/envelope/}Envelope')
            soap_body = ElementTree.SubElement(soap_env, '{http://schemas.xmlsoap.org/soap/envelope/}Body')
            soap_body.append(_soapy_services[soapaction.decode('UTF-8')](req).getroot())
            self.sendall_chunked(b"<?xml version='1.0' encoding='utf-8'?>" + ElementTree.tostring(soap_env, encoding='UTF-8'))
        except KeyError:
            logging.exception('400 Bad Request')
            self.request.sendall(b'HTTP/1.1 400 Bad Request\r\n\r\n')
        except Exception as e:
            logging.exception('500 Server Error')
            self.request.sendall(b'HTTP/1.1 500 Server Error\r\n\r\n')
        logging.debug('=====')

    def sendall_chunked(self, data, chunk_sz=2048):
        for i in range(0, len(data), chunk_sz):
            chunk = data[i:i+chunk_sz]
            self.request.sendall(b'%X\r\n%s\r\n' % (len(chunk), chunk))
        self.request.sendall(b'0\r\n\r\n')
        logging.debug('--> %s', data)
