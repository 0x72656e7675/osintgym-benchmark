import json
import sys
import urllib.request

card = json.load(sys.stdin)
page = urllib.request.urlopen(card["seed"][0], timeout=10).read().decode()
print(json.dumps({"status": "answered", "answer": {}, "evidence": [card["seed"][0]], "report": page[:20],
                  "usage": {"input_tokens": 7}}))
