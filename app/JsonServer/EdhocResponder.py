from bottle import route, run, request
import json

#============================ receive from manager ============================

@route('<path:path>', method='ANY')
def all(path):
    notif = json.loads(request.body.getvalue())
    print(notif)

run(host='localhost', port=1880, quiet=True)
