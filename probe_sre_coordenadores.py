import json
import urllib.request
import ssl

def probe():
    ctx = ssl.create_default_context()
    # using a recent known requerimento ID (e.g. 36735, 36800, etc. that were in the logs before)
    # Let's fetch one from the current dataset first.
    pass

if __name__ == '__main__':
    probe()
