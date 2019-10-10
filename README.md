# Redis Backed DSC
This proof of concept project will allow the IBM Security Access Manager Reverse Proxy (WebSEAL) DSC client to interface with a Redis.

While this demonstrates a Redis, you can essentially plugin in every backend.

# Prerequisites
You'll need the following Python modules:
```
pip install redis flask requests
```

# Docker
I have provided a Dockerfile as well, you can repackage if you want, it's as simple as running the following to build the image:
```
docker build -t dsconredis ./
```
Where "dsconredis" is the name of the image.
Afterwards, you can run it with:
```
docker run -d -e REDIS_HOST="redis.example.org" -e REDIS_PORT=6379 -e REDIS_DB=0 -e FLASK_SECRET="some secret for your flask" -e DEBUG_MODE="yes" -e PYTHONUNBUFFERED=TRUE -p 8080:80 dsconredis
```

The image is based on https://github.com/tiangolo/meinheld-gunicorn-flask-docker.

# IBM Security Access Manager
Once Redis is running, and the container is working, you can configure a Reverse Proxy (WebSEAL) to connect with the shim, the most important configuration is in `dsess` stanza:
```
[session]
dsess-enabled = yes
standard-junction-replica-set = default
[replica-sets]
replica-set = default
[dsess]
dsess-sess-id-pool-size = 125
dsess-cluster-name = dsess
[dsess-cluster]
server = 9,http://dockerip:8080/DSess/services/DSess
response-by = 60
handle-pool-size = 10
handle-idle-timeout = 30
timeout = 30
max-wait-time = 0
ssl-keyfile =
ssl-keyfile-stash =
ssl-keyfile-label =
load-balance = yes
```
You could add additional servers, and set `load-balance` to `yes` as the DSC is now in a complete active state (no more hot-standby shards).

# Fun
Finally, enjoy making new sessions on your ISAM knowing it's now backed by Redis! :)

# The Protocol
I have provided request/response examples from the DSC as a way to document the protocol. I've made assumptions on certain areas.