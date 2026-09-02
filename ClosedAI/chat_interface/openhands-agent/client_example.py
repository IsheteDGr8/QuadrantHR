import json

import requests

url = "http://127.0.0.1:8001/run"
prompt = "Write 3 facts about the current project into FACTS.txt."

response = requests.post(url, json={"prompt": prompt}, timeout=60)
response.raise_for_status()
print(response.text)
