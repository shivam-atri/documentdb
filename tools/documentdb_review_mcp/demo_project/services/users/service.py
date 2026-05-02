from http.server import BaseHTTPRequestHandler, HTTPServer
import json

USERS = {"1": {"id": "1", "name": "Ada"}, "2": {"id": "2", "name": "Linus"}}

class UsersHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path.startswith('/users/'):
            user_id = self.path.split('/')[-1]
            payload = USERS.get(user_id, {"error": "not-found", "id": user_id})
            self.send_response(200)
            self.end_headers()
            self.wfile.write(json.dumps(payload).encode('utf-8'))
        else:
            self.send_response(404)
            self.end_headers()


def run_users_service(host='127.0.0.1', port=8011):
    server = HTTPServer((host, port), UsersHandler)
    print(f'users service on {host}:{port}')
    server.serve_forever()


if __name__ == '__main__':
    run_users_service()
# review change
