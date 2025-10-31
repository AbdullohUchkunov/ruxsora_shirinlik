# 🚀 ERPNext Production Deployment Guide

## 📋 Tavsifnoma

Bu loyihada Frappe/ERPNext/HRMS ni Ubuntu 24.04 serverga production muhitida deploy qilish uchun avtomatik scriptlar mavjud.

**Server Specs:**
- OS: Ubuntu 24.04 Server
- RAM: 4GB
- CPU: 2 Core
- Disk: 80GB SSD
- Site: erp.local

**Apps:**
- Frappe Framework (v15)
- ERPNext (v15)
- HRMS (v15)
- ext_accounts (Custom App)

---

## 🎯 Deploy Jarayoni

### 1️⃣ Serverga Ulanish

```bash
ssh root@YOUR_SERVER_IP
```

### 2️⃣ Backup Fayllarni Serverga Ko'chirish

**Lokal kompyuterdan:**

```bash
# Backup fayllarni serverga yuklash
scp 20251031_195744-erp_localhost-database.sql.gz root@YOUR_SERVER_IP:/root/
scp 20251031_195744-erp_localhost-site_config_backup.json root@YOUR_SERVER_IP:/root/
```

**Yoki GitHub reposi orqali:**

```bash
# Serverda
git clone https://github.com/AbdullohUchkunov/ruxsora_shirinlik.git
cd ruxsora_shirinlik
```

### 3️⃣ Deploy Script Ishga Tushirish

```bash
# Script ga executable permission berish
chmod +x deploy_frappe_production.sh

# Deploy boshlash (1-2 soat davom etadi)
sudo bash deploy_frappe_production.sh
```

**Script qilgan ishlar:**
- ✅ Sistema yangilaydi
- ✅ Barcha dependencies o'rnatadi (Python, Node.js, MariaDB, Redis, nginx)
- ✅ Frappe Bench o'rnatadi
- ✅ ERPNext, HRMS, custom app o'rnatadi
- ✅ Site yaratadi (erp.local)
- ✅ Production setup qiladi (nginx, supervisor)
- ✅ Firewall sozlaydi

**Eslatma:** Script MariaDB root password so'raydi (2 marta):
1. MariaDB secure installation uchun
2. Site yaratish uchun

### 4️⃣ Backup Restore Qilish

```bash
# Backup fayllarni frappe user papkasiga ko'chirish
sudo mkdir -p /home/frappe/backups
sudo cp 20251031_195744-erp_localhost-database.sql.gz /home/frappe/backups/
sudo cp 20251031_195744-erp_localhost-site_config_backup.json /home/frappe/backups/
sudo chown -R frappe:frappe /home/frappe/backups

# Restore script ishga tushirish
chmod +x restore_backup.sh
sudo bash restore_backup.sh
```

### 5️⃣ Site Tekshirish

```bash
# Site ochiq ekanligini tekshirish
curl http://localhost

# Browser orqali
http://YOUR_SERVER_IP
```

**Login Ma'lumotlari:**
- Username: `Administrator`
- Password: `admin` (yoki backup dagi eski parol)

---

## 🔧 Foydali Buyruqlar

### Bench Buyruqlari

```bash
# Frappe user ga o'tish
sudo su - frappe

# Bench katalogiga o'tish
cd frappe-bench

# Site statusini ko'rish
bench --site erp.local status

# Loglarni ko'rish
bench --site erp.local logs

# Console ochish (Python shell)
bench --site erp.local console

# Database backup olish
bench --site erp.local backup

# Site yangilash
bench update

# Cache tozalash
bench --site erp.local clear-cache

# Migrate qilish
bench --site erp.local migrate
```

### Supervisor (Process Manager)

```bash
# Barcha processlarni qayta ishga tushirish
sudo supervisorctl restart all

# Statusni ko'rish
sudo supervisorctl status

# Alohida process restart qilish
sudo supervisorctl restart frappe-bench-web:
```

### Nginx

```bash
# Nginx restart
sudo systemctl restart nginx

# Nginx statusini ko'rish
sudo systemctl status nginx

# Nginx configni tekshirish
sudo nginx -t
```

### MariaDB

```bash
# MariaDB ga ulanish
sudo mysql -u root -p

# Database ro'yxati
SHOW DATABASES;

# Backup olish (manual)
mysqldump -u root -p DATABASE_NAME | gzip > backup.sql.gz
```

---

## 🌐 Domain Ulash (Keyinchalik)

Bir hafta keyin domain ulasangiz:

### 1. DNS Sozlash

```
A Record: @ -> YOUR_SERVER_IP
A Record: www -> YOUR_SERVER_IP
```

### 2. Site Rename Qilish

```bash
sudo su - frappe
cd frappe-bench

# Site nomini o'zgartirish
bench --site erp.local rename-site yourdomain.com

# Nginx config yangilash
sudo bench setup nginx
sudo systemctl restart nginx
```

### 3. SSL O'rnatish (Let's Encrypt)

```bash
# Certbot o'rnatish
sudo apt install certbot python3-certbot-nginx -y

# SSL sertifikat olish
sudo bench setup lets-encrypt erp.local --custom-domain yourdomain.com
```

---

## 🔐 Xavfsizlik

### 1. Administrator Parolni O'zgartirish

Site ga kirib:
1. User icon → My Settings
2. Change Password
3. Yangi qattiq parol qo'ying

### 2. Firewall

```bash
# Faqat kerakli portlarni ochish
sudo ufw allow 22/tcp   # SSH
sudo ufw allow 80/tcp   # HTTP
sudo ufw allow 443/tcp  # HTTPS
sudo ufw enable
```

### 3. SSH Key Authentication

```bash
# Lokal kompyuterda SSH key yaratish
ssh-keygen -t rsa -b 4096

# Public key ni serverga ko'chirish
ssh-copy-id root@YOUR_SERVER_IP

# Password authentication o'chirish (opsional)
sudo nano /etc/ssh/sshd_config
# PasswordAuthentication no
sudo systemctl restart sshd
```

---

## 💾 Automatic Backup Setup

### Kunlik Backup (Cron)

```bash
sudo su - frappe
cd frappe-bench

# Backup script yaratish
cat > backup.sh << 'EOF'
#!/bin/bash
cd /home/frappe/frappe-bench
bench --site erp.local backup --with-files
EOF

chmod +x backup.sh

# Cron job qo'shish (har kecha soat 2 da)
crontab -e
# Quyidagini qo'shing:
0 2 * * * /home/frappe/frappe-bench/backup.sh >> /home/frappe/backup.log 2>&1
```

### Backup ni Cloud ga Yuklash

```bash
# AWS S3, DigitalOcean Spaces, yoki Dropbox bilan integratsiya
bench config --global set-common-config -c backup_s3_bucket "your-bucket-name"
```

---

## 📊 Monitoring (Opsional)

### Server Monitoring

```bash
# htop o'rnatish
sudo apt install htop -y

# Real-time monitoring
htop
```

### Frappe Bench Logs

```bash
# Real-time logs
tail -f ~/frappe-bench/sites/erp.local/logs/web.log
tail -f ~/frappe-bench/sites/erp.local/logs/worker.log
tail -f ~/frappe-bench/sites/erp.local/logs/schedule.log
```

---

## ❗ Troubleshooting

### Site Ochilmayotgan Bo'lsa

```bash
# Nginx va supervisor statusini tekshiring
sudo systemctl status nginx
sudo supervisorctl status

# Portlar ochiq ekanligini tekshiring
sudo netstat -tlnp | grep -E '(80|443|8000)'

# Loglarni ko'ring
sudo tail -f /var/log/nginx/error.log
bench --site erp.local logs
```

### Database Xatoliklari

```bash
# MariaDB ishlayotganini tekshiring
sudo systemctl status mariadb

# Database ga ulanib ko'ring
sudo mysql -u root -p
```

### Permission Issues

```bash
# Barcha fayllar frappe user ga tegishli bo'lishi kerak
sudo chown -R frappe:frappe /home/frappe/frappe-bench
```

### Disk Space To'lgan Bo'lsa

```bash
# Disk space tekshirish
df -h

# Eski backuplarni o'chirish
cd ~/frappe-bench/sites/erp.local/private/backups
ls -lh
rm old_backup.sql.gz
```

---

## 📞 Support

**Savollar bo'lsa:**
- Frappe Forum: https://discuss.frappe.io
- ERPNext Docs: https://docs.erpnext.com
- GitHub Issues: https://github.com/frappe/erpnext/issues

---

## 📝 Changelog

- **2025-10-31**: Initial deployment setup
  - Ubuntu 24.04 Server
  - Frappe v15, ERPNext v15, HRMS v15
  - Site: erp.local
  - Custom app: ext_accounts

---

## ✅ Keyingi Qadamlar

- [ ] Deploy scriptni ishga tushirish
- [ ] Backup restore qilish
- [ ] Administrator parolni o'zgartirish
- [ ] Automatic backup sozlash
- [ ] Domain ulash (1 hafta keyin)
- [ ] SSL o'rnatish
- [ ] Monitoring sozlash
- [ ] Users yaratish va permissions berish

---

**Omad! 🚀**
