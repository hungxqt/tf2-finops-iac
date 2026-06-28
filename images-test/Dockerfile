FROM nginx:alpine

# Copy local index.html to the default Nginx public directory
COPY index.html /usr/share/nginx/html/index.html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
