---
title: 'Clean install OptiSigns on Raspberry Pi/Linux'
article_id: 4411956075027
section: 'Raspberry Pi / Linux'
source_url: https://support.optisigns.com/hc/en-us/articles/4411956075027-Clean-install-OptiSigns-on-Raspberry-Pi-Linux
updated_at: 2026-09-10T09:47:36Z
content_hash: 4bec951f0ff2ba4fee658917d76e77c6
---

Article URL: https://support.optisigns.com/hc/en-us/articles/4411956075027-Clean-install-OptiSigns-on-Raspberry-Pi-Linux

# Clean install OptiSigns on Raspberry Pi/Linux

To completely clean out old installation of OptiSigns on Linux or Raspberry Pi

Please run:

```
rm -rf ~/.config/OptiSignsrm ~/.config/autostart/'OptiSigns Digital Signage.desktop'
```

Also delete the long string text on this ~/.config folder

Then install the new AppImage download from <https://www.optisigns.com/download>
