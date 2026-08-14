from urllib.parse import unquote
from lzstring import LZString

compressed = "N4IgjCBcoLQExVAYygFwE4FcCmAaEA9lANogCsIAugL7X4XQgAOUc%2BTLkYADN7UA"

decoded = unquote(compressed)
result = LZString.decompressFromEncodedURIComponent(decoded)

print(result)
