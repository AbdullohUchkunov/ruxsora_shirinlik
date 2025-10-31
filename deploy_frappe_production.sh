#!/bin/bash

###############################################################################
# Frappe/ERPNext/HRMS Production Deployment Script
# Ubuntu 24.04 Server
# Site: erp.local
# Author: GitHub Copilot
# Date: 2025-10-31
###############################################################################

set -e  # Exit on error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Configuration
FRAPPE_USER="frappe"
SITE_NAME="erp.local"
FRAPPE_VERSION="version-15"
ERPNEXT_VERSION="version-15"
HRMS_VERSION="version-15"
BENCH_PATH="/home/${FRAPPE_USER}/frappe-bench"
MYSQL_ROOT_PASSWORD=""  # Will be set during installation

# Logging function
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

# Check if running as root
check_root() {
    if [ "$EUID" -ne 0 ]; then 
        error "Bu scriptni root user sifatida ishga tushiring: sudo bash deploy_frappe_production.sh"
    fi
}

# System update
update_system() {
    log "Sistema yangilanmoqda..."
    apt-get update -y
    apt-get upgrade -y
    log "Sistema muvaffaqiyatli yangilandi ✓"
}

# Install dependencies
install_dependencies() {
    log "Dependencies o'rnatilmoqda..."
    
    # Basic dependencies
    apt-get install -y \
        git \
        python3-dev \
        python3-pip \
        python3-setuptools \
        python3-venv \
        software-properties-common \
        mariadb-server \
        mariadb-client \
        redis-server \
        xvfb \
        libfontconfig \
        wkhtmltopdf \
        libmysqlclient-dev \
        curl \
        supervisor \
        nginx \
        build-essential \
        htop \
        vim

    log "Dependencies muvaffaqiyatli o'rnatildi ✓"
}

# Install Node.js 18
install_nodejs() {
    log "Node.js 18 o'rnatilmoqda..."
    
    curl -fsSL https://deb.nodesource.com/setup_18.x | bash -
    apt-get install -y nodejs
    
    npm install -g yarn
    
    log "Node.js version: $(node -v)"
    log "npm version: $(npm -v)"
    log "yarn version: $(yarn -v)"
    log "Node.js muvaffaqiyatli o'rnatildi ✓"
}

# Configure MariaDB
configure_mariadb() {
    log "MariaDB sozlanmoqda..."
    
    # MariaDB configuration for Frappe
    cat > /etc/mysql/mariadb.conf.d/frappe.cnf << EOF
[mysqld]
character-set-client-handshake = FALSE
character-set-server = utf8mb4
collation-server = utf8mb4_unicode_ci

[mysql]
default-character-set = utf8mb4
EOF

    systemctl restart mariadb
    systemctl enable mariadb
    
    # Secure MariaDB installation
    log "MariaDB uchun root password o'rnating..."
    mysql_secure_installation
    
    log "MariaDB sozlandi ✓"
}

# Create Frappe user
create_frappe_user() {
    log "Frappe user yaratilmoqda..."
    
    if id "$FRAPPE_USER" &>/dev/null; then
        warning "User '$FRAPPE_USER' allaqachon mavjud"
    else
        adduser --disabled-password --gecos "" $FRAPPE_USER
        usermod -aG sudo $FRAPPE_USER
        log "User '$FRAPPE_USER' yaratildi ✓"
    fi
}

# Install Frappe Bench
install_bench() {
    log "Frappe Bench o'rnatilmoqda..."
    
    # Switch to frappe user
    sudo -u $FRAPPE_USER bash << EOF
set -e

# Install bench
pip3 install frappe-bench

# Add local bin to PATH
echo 'export PATH=\$PATH:~/.local/bin' >> ~/.bashrc
export PATH=\$PATH:~/.local/bin

# Initialize bench
cd /home/$FRAPPE_USER
bench init --frappe-branch $FRAPPE_VERSION frappe-bench

cd frappe-bench

# Install ERPNext
bench get-app --branch $ERPNEXT_VERSION erpnext

# Install HRMS
bench get-app --branch $HRMS_VERSION hrms

# Install custom app (ruxsora_shirinlik)
bench get-app https://github.com/AbdullohUchkunov/ruxsora_shirinlik.git

EOF

    log "Frappe Bench o'rnatildi ✓"
}

# Create site
create_site() {
    log "Site '$SITE_NAME' yaratilmoqda..."
    
    sudo -u $FRAPPE_USER bash << EOF
set -e
cd $BENCH_PATH
export PATH=\$PATH:~/.local/bin

# Create new site
bench new-site $SITE_NAME --admin-password admin --db-root-password $MYSQL_ROOT_PASSWORD

# Install apps
bench --site $SITE_NAME install-app erpnext
bench --site $SITE_NAME install-app hrms
bench --site $SITE_NAME install-app ext_accounts

EOF

    log "Site '$SITE_NAME' yaratildi ✓"
}

# Setup production
setup_production() {
    log "Production setup qilinmoqda..."
    
    sudo -u $FRAPPE_USER bash << EOF
set -e
cd $BENCH_PATH
export PATH=\$PATH:~/.local/bin

# Setup production with supervisor and nginx
sudo bench setup production $FRAPPE_USER --yes

# Enable scheduler
bench --site $SITE_NAME scheduler enable

# Setup nginx
sudo bench setup nginx --yes

EOF

    systemctl restart supervisor
    systemctl restart nginx
    systemctl enable supervisor
    systemctl enable nginx
    
    log "Production setup tugadi ✓"
}

# Configure firewall
configure_firewall() {
    log "Firewall sozlanmoqda..."
    
    if command -v ufw &> /dev/null; then
        ufw allow 22/tcp
        ufw allow 80/tcp
        ufw allow 443/tcp
        ufw --force enable
        log "Firewall sozlandi ✓"
    else
        warning "ufw topilmadi, firewall sozlanmadi"
    fi
}

# Print completion message
print_completion() {
    log "=================================="
    log "DEPLOYMENT MUVAFFAQIYATLI TUGADI! 🎉"
    log "=================================="
    echo ""
    info "Site URL: http://$(hostname -I | awk '{print $1}')"
    info "Site Name: $SITE_NAME"
    info "Admin Username: Administrator"
    info "Admin Password: admin"
    echo ""
    warning "MUHIM: Administrator parolini o'zgartiring!"
    echo ""
    info "Keyingi qadamlar:"
    info "1. Backup restore qilish: bash restore_backup.sh"
    info "2. Domain ulagandan keyin SSL o'rnatish"
    info "3. Automatic backup sozlash"
    echo ""
    info "Foydalanish uchun foydali buyruqlar:"
    info "- Bench katalogiga o'tish: cd $BENCH_PATH"
    info "- Site statusini ko'rish: bench --site $SITE_NAME status"
    info "- Loglarni ko'rish: bench --site $SITE_NAME logs"
    info "- Restart qilish: sudo supervisorctl restart all"
    log "=================================="
}

# Main function
main() {
    log "Frappe/ERPNext/HRMS Production Deployment boshlandi..."
    echo ""
    
    check_root
    
    read -p "MariaDB root password kiriting: " MYSQL_ROOT_PASSWORD
    echo ""
    
    update_system
    install_dependencies
    install_nodejs
    configure_mariadb
    create_frappe_user
    install_bench
    
    read -p "MariaDB root password qayta kiriting (site yaratish uchun): " MYSQL_ROOT_PASSWORD
    create_site
    
    setup_production
    configure_firewall
    print_completion
}

# Run main function
main
