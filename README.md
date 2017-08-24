Soapy is a very simple python module to help creating mock SOAP services.
Soapy supports chunked requests.

Example
=======

```python3
import soapy
from xml.etree import ElementTree as ET

@soapy.service(action='sayHello')
def say_hello(req : ET.Element) -> ET.Element:
    return ET.fromstring('''
        <msg:Response xmlns:msg="http://example.org/soap/messages">
            <msg:SayHelloResp>Hello</msg:SayHelloResp>
        </msg:Response>
        ''')

soapy.run(port=5000)
```
Installation
============

```
pip install --user https://github.com/andirady/soapy.git
```
