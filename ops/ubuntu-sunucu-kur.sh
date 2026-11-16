#!/usr/bin/env bash
# Monster doğal Ubuntu Server hazırlığı (15 Kas 2026; WSL2'den taşıma). sudo ile bir kez çalıştırılır, idempotent.
# Docker (Ubuntu paketleri), Tailscale (resmî depo), kapak kapanınca uyumama, otomatik güvenlik güncellemesi
# (kendiliğinden yeniden başlatma yok). Tailscale oturumu ayrıca: sudo tailscale up --hostname=hipc --operator=<kullanıcı>
set -euo pipefail
[[ $EUID -eq 0 ]] || { echo "sudo ile çalıştırın"; exit 1; }
KULLANICI="${SUDO_USER:-ascendia}"
. /etc/os-release
export DEBIAN_FRONTEND=noninteractive

echo "== Docker"
apt-get update -q
apt-get install -y -q docker.io docker-compose-v2 curl ca-certificates unattended-upgrades
usermod -aG docker "$KULLANICI"
systemctl enable --now docker

echo "== Tailscale (resmî depo, $VERSION_CODENAME)"
if ! command -v tailscale >/dev/null; then
  curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/$VERSION_CODENAME.noarmor.gpg" -o /usr/share/keyrings/tailscale-archive-keyring.gpg
  curl -fsSL "https://pkgs.tailscale.com/stable/ubuntu/$VERSION_CODENAME.tailscale-keyring.list" -o /etc/apt/sources.list.d/tailscale.list
  apt-get update -q && apt-get install -y -q tailscale
fi
systemctl enable --now tailscaled

echo "== Kapak kapanınca ve boşta uyumasın (dizüstü sunucu)"
mkdir -p /etc/systemd/logind.conf.d
cat > /etc/systemd/logind.conf.d/10-ascendia-sunucu.conf <<'C'
[Login]
HandleLidSwitch=ignore
HandleLidSwitchExternalPower=ignore
HandleLidSwitchDocked=ignore
IdleAction=ignore
C
systemctl mask sleep.target suspend.target hibernate.target hybrid-sleep.target >/dev/null
systemctl kill -s HUP systemd-logind || true   # ayarı oturumları kesmeden yeniden okur

echo "== Otomatik güvenlik güncellemesi (yeniden başlatma yok; çekirdek güncellemesi sonrası yeniden başlatma elle)"
cat > /etc/apt/apt.conf.d/52ascendia-otomatik <<'C'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
Unattended-Upgrade::Automatic-Reboot "false";
C

echo "== Özet"
docker --version; docker compose version | head -1; tailscale version | head -1
systemctl is-enabled docker tailscaled
echo "KURULUM-TAMAM (Docker grubu için yeniden giriş gerekir)"
