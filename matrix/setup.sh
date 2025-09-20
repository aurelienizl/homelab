# !/bin/bash
set -e

# Generate the synapse configuration files
docker compose run --rm synapse

# Start the synapse server
docker compose up -d 

# Wait for the server to be fully up and running
sleep 30

# Create users 
docker compose exec synapse register_new_matrix_user \
  -c /data/homeserver.yaml -c /data/extra-config.yaml \
  http://localhost:8008 -u user1 -p '12345678' -a

docker compose exec synapse register_new_matrix_user \
  -c /data/homeserver.yaml -c /data/extra-config.yaml \
  http://localhost:8008 -u user2 -p '12345678' -a