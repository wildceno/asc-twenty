# Ascendia Pano (Twenty uygulaması)

Dashboard'a eklenen özel bileşenler (front component). Twenty çekirdeğine dokunmaz; Twenty uygulama çatısıyla
(`twenty` CLI, TypeScript/React) geliştirilir.

Dashboard widget'ları (her biri ayrı front component; Dashboard'a eklenip çıkarılabilir):
- **Pano Filtresi** (`pano-filtresi.tsx`): dönem (‹ yıl ›, tüm yıl, Q1–Q4, aylar, tüm zamanlar), kişi, aşama.
  Seçim sayfanın adresine yazılır (`ap_donem`, `ap_kisi`, `ap_asama`); sayfadaki tüm Ascendia widget'ları okur.
  Filtre widget'ı yoksa varsayılan: içinde bulunulan çeyrek, herkes, Lost/DSQ hariç aşamalar.
- **Satış Göstergeleri**, **Hedef Takibi**, **Aşama Dağılımı**, **Büyük Fırsatlar**, **Fırsat Dökümü**
  (Fırsat Dökümü eski Satış Panosu'nun kimliğini kullanır).
- Ortak katman: `src/lib/pano-veri.ts` (veri, mali dönem), `src/lib/filtre.ts` (adres filtresi),
  `src/lib/hesap.ts` (süzme, hedef, toplamlar), `src/lib/ui.tsx` (Twenty tema değişkenleri, SVG grafikler).

Veri panoya bakan kişinin yetkisiyle okunur. Sandbox'ta canvas ve DOM ölçümü yok: grafikler SVG + d3-scale.

Geliştirme ve kurulum (sunucuda, Node 24 + Yarn 4; Monster'da `~/.local/araclar/node24`):
```
export PATH=$HOME/.local/araclar/node24/bin:$PATH
cd ~/ascendia-crm/apps/ascendia-pano
corepack yarn install
corepack yarn twenty app apply            # ilk kez: --create
```
CLI uzak sunucu: `twenty auth login --with-token --url http://localhost:3010 --name monster --use < ~/twenty/.twenty-api-key`
