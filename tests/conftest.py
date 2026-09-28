import os

# today.py reads ACCESS_TOKEN at import time; tests never make real requests
os.environ.setdefault('ACCESS_TOKEN', 'test-token-not-real')
