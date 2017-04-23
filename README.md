# medipay_new
Medipay web-application

To run it with working SocketIO functionality, you should run the gunicorn server using the following command:

gunicorn --worker-class eventlet -b 0.0.0.0:8080 -w 1 wsgi

And configure your apache VirtualHost as per example:
<VirtualHost *:80>
  ServerName yourdomain.com
  ServerAlias www.youdomain.com
  DocumentRoot /path_to_app/project/static
  Alias /static /path_to_app/project/static

  RewriteEngine On
  RewriteCond %{REQUEST_URI}  ^/socket.io            [NC]
  RewriteCond %{QUERY_STRING} transport=websocket    [NC]
  RewriteRule /(.*)           ws://127.0.0.1:8080/$1 [P,L]

  ProxyPreserveHost On

  ProxyPass /static !

  ProxyPass / http://127.0.0.1:8080/
  ProxyPassReverse / http://127.0.0.1:8080/
</VirtualHost>

Apache here works as a reverse proxy to your gunicorn server.

WARNING: eventlet version should be 0.17.4 (actually just not 0.18 and higher) as it's the most stable when working with SocketIO
