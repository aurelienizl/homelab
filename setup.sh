################################
# Nextcloud initial setup
################################

docker compose exec -u www-data nextcloud php occ config:system:set maintenance_window_start --type=integer --value=3
docker compose exec -u www-data nextcloud php occ maintenance:repair --include-expensive
docker compose exec -u www-data nextcloud php occ db:add-missing-indices
docker compose exec -u www-data nextcloud php occ config:system:set default_phone_region --value=FR
docker compose exec -u www-data nextcloud php occ background:cron

##############################
# Apps installation
##############################

# Richdocuments -> must be configured manually after installation
docker compose exec -u www-data nextcloud php occ app:install richdocuments
docker compose exec -u www-data nextcloud php occ app:enable richdocuments

# Files Antivirus -> must be configured manually after installation
docker compose exec -u www-data nextcloud php occ app:install files_antivirus
docker compose exec -u www-data nextcloud php occ app:enable files_antivirus

##############################
# Reverse proxy setup
##############################

set -a
source .env
set +a

docker compose exec -u www-data nextcloud php occ config:system:set trusted_proxies 0 --value="$TRUSTED_PROXIES"
docker compose exec -u www-data nextcloud php occ config:system:set trusted_domains 1 --value="$NEXTCLOUD_DOMAIN"
docker compose exec -u www-data nextcloud php occ config:system:set overwritehost --value="$NEXTCLOUD_DOMAIN"
docker compose exec -u www-data nextcloud php occ config:system:set overwriteprotocol --value="https"
docker compose exec -u www-data nextcloud php occ config:system:set overwrite.cli.url --value="https://$NEXTCLOUD_DOMAIN"
