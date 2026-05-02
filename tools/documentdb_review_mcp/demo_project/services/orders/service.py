from http.server import BaseHTTPRequestHandler, HTTPServer
import json

ORDERS = {"100": {"order_id": "100", "user_id": "1", "total": 120.0}}

class OrdersHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/orders/'):
            order_id = self.path.split('/')[-1]
            payload = ORDERS.get(order_id, {"error": "not-found"})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()


def run_orders_service(host='127.0.0.1', port=8012):
    server = HTTPServer((host, port), OrdersHandler)
    print(f'orders service on {host}:{port}')
    server.serve_forever()


if __name__ == '__main__':
    run_orders_service()
