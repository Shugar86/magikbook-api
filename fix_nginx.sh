sed -i 's/location \/ {/location \/uploads\/ {\n        proxy_pass http:\/\/localhost:8000\/uploads\/;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n    }\n\n    location \/ {/g' /etc/nginx/sites-enabled/magikbook.ru.conf
systemctl reload nginx
