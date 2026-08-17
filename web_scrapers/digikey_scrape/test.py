from urllib.parse import unquote
from lzstring import LZString
import base64
import json

de = "eyJDYXRlZ29yaWVzIjp7InNlbGVjdGlvbiI6W3sidmFsdWUiOiJUaGVybWFsICYgVGhlcm1hbCBNYWduZXRpYyBDaXJjdWl0IEJyZWFrZXJzIiwiaGlkZGVuX3BheWxvYWQiOnsiTGV2ZWwiOjN9fV0sIm1haW5fbGFiZWwiOiJDYXRlZ29yeSJ9fQ%3D%3D"
de = unquote(de)
decode = base64.b64decode(de)
decode = {
    "Categories": {
        "selection": [
            {
                "value": "Thermal & Thermal Magnetic Circuit Breakers",
                "hidden_payload": {"Level": 1},
            }
        ],
        "main_label": "Category",
    }
}
selection = decode["Categories"]["selection"]
selection[0]["value"] = "Other Audio &DVideo Connectors"
compact_json = json.dumps(
    decode,
    separators=(",", ":"),
    ensure_ascii=False,
).encode()
print(base64.b64encode(compact_json))
