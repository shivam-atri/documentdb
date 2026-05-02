"""Gateway service that calls multiple downstream services."""
from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.request import urlopen
import json

USERS_SERVICE_URL = 'http://127.0.0.1:8011'
ORDERS_SERVICE_URL = 'http://127.0.0.1:8012'


def fetch_json(url):
    with urlopen(url, timeout=3) as response:
        return json.loads(response.read().decode('utf-8'))


class GatewayHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/profile/'):
            user_id = self.path.split('/')[-1]
            user = fetch_json(f"{USERS_SERVICE_URL}/users/{user_id}")
            order = fetch_json(f"{ORDERS_SERVICE_URL}/orders/100")
            payload = {"user": user, "latest_order": order}
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()


def run_gateway_service(host='127.0.0.1', port=8010):
    server = HTTPServer((host, port), GatewayHandler)
    print(f'gateway service on {host}:{port}')
    server.serve_forever()


if __name__ == '__main__':
    run_gateway_service()

# service timeout tuning
# delta
