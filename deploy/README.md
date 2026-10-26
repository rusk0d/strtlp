# Deploying the startlap reader on a VPS

Assumes Ubuntu or Debian, a domain pointing at the VPS, and root access.

## 1. Install
    sudo apt update && sudo apt install -y python3 caddy
    sudo useradd --system --home /srv/startlap --shell /usr/sbin/nologin startlap
    sudo mkdir -p /srv/startlap && sudo chown startlap: /srv/startlap
    sudo cp build.py /srv/startlap/        # the builder from the project folder
    sudo chown startlap: /srv/startlap/build.py
    sudo touch /var/log/startlap.log && sudo chown startlap: /var/log/startlap.log

## 2. Build once
    sudo -u startlap python3 -I /srv/startlap/build.py

## 3. Schedule it
    sudo crontab -u startlap crontab.txt

## 4. Serve it behind a password
    caddy hash-password                   # enter a password, copy the hash
    sudo nano /etc/caddy/Caddyfile        # paste Caddyfile, set domain, user, hash
    sudo systemctl reload caddy

Open https://strlp.ruskodavid.hu/ and log in. Caddy renews the HTTPS certificate on its own.

## Notes
- Open ports 80 and 443 in the VPS firewall. Nothing else needs to be exposed.
- Use one login per person, or share one, but change the password if it leaks.
- The cron job runs every 30 minutes and only fetches articles it hasn't seen.
- Check the log with: tail /var/log/startlap.log
