#!/bin/bash

###############################################################################
# Backup Restore Script for Frappe ERPNext
# Restores database and site configuration from backup files
# Site: erp.local
###############################################################################

set -e

# Colors
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
FRAPPE_USER="frappe"
SITE_NAME="erp.local"
BENCH_PATH="/home/${FRAPPE_USER}/frappe-bench"
BACKUP_DIR="/home/${FRAPPE_USER}/backups"

# File paths (update these with actual backup file names)
SQL_BACKUP="20251031_195744-erp_localhost-database.sql.gz"
CONFIG_BACKUP="20251031_195744-erp_localhost-site_config_backup.json"

log() {
    echo -e "${GREEN}[$(date +'%Y-%m-%d %H:%M:%S')]${NC} $1"
}

error() {
    echo -e "${RED}[ERROR]${NC} $1"
    exit 1
}

warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

check_backup_files() {
    log "Backup fayllar tekshirilmoqda..."
    
    if [ ! -f "$BACKUP_DIR/$SQL_BACKUP" ]; then
        error "SQL backup fayl topilmadi: $BACKUP_DIR/$SQL_BACKUP"
    fi
    
    if [ ! -f "$BACKUP_DIR/$CONFIG_BACKUP" ]; then
        warning "Config backup fayl topilmadi: $BACKUP_DIR/$CONFIG_BACKUP"
        info "Config fayl siz davom ettiriladi..."
    fi
    
    log "Backup fayllar topildi ✓"
}

restore_database() {
    log "Database restore qilinmoqda..."
    
    sudo -u $FRAPPE_USER bash << EOF
set -e
cd $BENCH_PATH
export PATH=\$PATH:~/.local/bin

# Stop site
bench --site $SITE_NAME set-maintenance-mode on

# Get database name
DB_NAME=\$(bench --site $SITE_NAME config db_name | tail -1)

# Restore database
log "Database: \$DB_NAME"
gunzip < $BACKUP_DIR/$SQL_BACKUP | mysql -u root -p\$MYSQL_ROOT_PASSWORD \$DB_NAME

# Migrate
bench --site $SITE_NAME migrate

# Clear cache
bench --site $SITE_NAME clear-cache

# Restart
bench --site $SITE_NAME set-maintenance-mode off

EOF

    log "Database muvaffaqiyatli restore qilindi ✓"
}

restore_site_config() {
    if [ -f "$BACKUP_DIR/$CONFIG_BACKUP" ]; then
        log "Site config restore qilinmoqda..."
        
        sudo -u $FRAPPE_USER bash << EOF
set -e
cd $BENCH_PATH

# Backup current config
cp sites/$SITE_NAME/site_config.json sites/$SITE_NAME/site_config.json.backup

# Merge configs (keep new db credentials, restore other settings)
python3 << PYTHON
import json

# Read old config
with open('$BACKUP_DIR/$CONFIG_BACKUP', 'r') as f:
    old_config = json.load(f)

# Read new config
with open('sites/$SITE_NAME/site_config.json', 'r') as f:
    new_config = json.load(f)

# Keep new database credentials
if 'db_name' in new_config:
    old_config['db_name'] = new_config['db_name']
if 'db_password' in new_config:
    old_config['db_password'] = new_config['db_password']

# Write merged config
with open('sites/$SITE_NAME/site_config.json', 'w') as f:
    json.dump(old_config, f, indent=1)

print("Config merged successfully")
PYTHON

EOF
        
        log "Site config restore qilindi ✓"
    else
        info "Site config fayl topilmadi, skip qilindi"
    fi
}

restart_services() {
    log "Servislar qayta ishga tushirilmoqda..."
    
    sudo supervisorctl restart all
    sudo systemctl restart nginx
    
    log "Servislar qayta ishga tushirildi ✓"
}

print_completion() {
    log "=================================="
    log "BACKUP RESTORE TUGADI! 🎉"
    log "=================================="
    echo ""
    info "Site: $SITE_NAME"
    info "URL: http://$(hostname -I | awk '{print $1}')"
    echo ""
    info "Site ga kirishingiz mumkin!"
    echo ""
    warning "Agar xatolik bo'lsa, loglarni tekshiring:"
    info "bench --site $SITE_NAME logs"
    log "=================================="
}

main() {
    log "Backup restore boshlandi..."
    echo ""
    
    if [ "$EUID" -ne 0 ]; then 
        error "Bu scriptni root user sifatida ishga tushiring: sudo bash restore_backup.sh"
    fi
    
    # Create backup directory if not exists
    sudo -u $FRAPPE_USER mkdir -p $BACKUP_DIR
    
    # Check if backup files are in backup directory
    if [ ! -f "$BACKUP_DIR/$SQL_BACKUP" ]; then
        info "Backup fayllarni $BACKUP_DIR ga ko'chiring"
        info "Masalan: sudo cp /path/to/backups/*.{sql.gz,json} $BACKUP_DIR/"
        info "        sudo chown $FRAPPE_USER:$FRAPPE_USER $BACKUP_DIR/*"
        error "Backup fayllar topilmadi"
    fi
    
    read -sp "MariaDB root password kiriting: " MYSQL_ROOT_PASSWORD
    echo ""
    export MYSQL_ROOT_PASSWORD
    
    check_backup_files
    restore_database
    restore_site_config
    restart_services
    print_completion
}

main
