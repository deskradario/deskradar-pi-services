cp services/* /etc/systemd/system/
systemctl enable deskradar.service
systemctl enable deskradar-lcd.service
systemctl enable deskradar-ap.service