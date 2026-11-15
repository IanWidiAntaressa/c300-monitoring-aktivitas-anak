import uvicorn
from backend import config
c = config.load()
uvicorn.run("backend.main:app", host=c["host"], port=c["port"])
