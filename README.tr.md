# quickshell-kde

> **KDE Plasma 6 ve KWin Wayland için [Quickshell](https://quickshell.outfoxxed.me) ile geliştirilmiş birleştirilebilir, KDE-yerel masaüstü kabuk katmanları (Bar, Dock, Başlatıcı, Açılır Pencereler ve OSD).**
>
> *[Sena](https://github.com/SnTR370) tarafından geliştirilmekte ve sürdürülmektedir.*

[English](README.md) · [Türkçe](README.tr.md)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](LICENSE)
[![Platform: KDE Plasma 6 | KWin Wayland](https://img.shields.io/badge/Platform-KDE%20Plasma%206%20%7C%20KWin%20Wayland-1d99f3)](https://kde.org/plasma-desktop/)
[![Quickshell: 0.3.0+](https://img.shields.io/badge/Quickshell-0.3.0%2B-7c3aed)](https://quickshell.outfoxxed.me)
[![Qt6 / QML](https://img.shields.io/badge/Qt6-QML-41cd52)](https://www.qt.io/)

[**Genel Bakış**](#kdekwin-yerel-yapan-nedir) · [**Özellikler ve Durum**](#öne-çıkan-özellikler-ve-doğrulama-durumu) · [**Karşılaştırma**](#ekosistem-karşılaştırması) · [**Mimari**](#mimari-genel-bakış) · [**Hızlı Başlangıç**](#hızlı-başlangıç) · [**Yapılandırma**](#yapılandırma-ve-özelleştirme) · [**Belgeler**](#belgeler)

---

## Genel Bakış

**quickshell-kde**, bildirimsel (declarative) QML/Quickshell özelleştirmelerini—yüzen barlar, yuva (slot) tabanlı modüller, büyüten dock'lar, çıpalı (anchored) açılır pencereler ve JSON tabanlı temalar—Hyprland, Niri veya Sway gibi bağımsız döşemeli (tiling) bir pencere yöneticisine geçmenize gerek kalmadan doğrudan **KWin Wayland üzerindeki KDE Plasma 6** ortamına getirir.

### Dal Durumu (`feat/composable-shell-ux` ve `main`)

| Dal (Branch) | Aşama (Milestone) | Dahil Edilen Yeteneklerin Özeti |
| :--- | :--- | :--- |
| **`feat/composable-shell-ux`** *(Aktif Geliştirme)* | **Milestone 3A** | 4 kenarlı birleştirilebilir Bar/Dock yüzeyleri, sıfır-strut yüzen varsayılanlar, `ModuleRegistry` yuva yerleşimi, `AnchoredPopup` açılır pencereleri (`AudioPopup`, `BrightnessPopup`, `MediaPopup`, `PowerPopup`, `WindowChooserPopup`), SNI sistem çekmecesi öğe bazlı görünürlük politikaları (`auto`/`always`/`hidden`) ve taşma açılır penceresi, deterministik KWin pencere kimliği ve meta veri önbelleği, UUID hedefli KWin 6 pencere eylemleri (odaklama, simge durumuna küçültme geçişi, zarif kapatma, ekrana taşıma) ve 20 otomatik birim/çalışma zamanı regresyon testi. |
| **`main`** *(Temel Kararlı Sürüm)* | **Milestone 2** | İlk KWin Wayland D-Bus entegrasyonu, üst/yan bar, otomatik gizlenen büyüten dock, Spotlight tarzı başlatıcı, PipeWire ses, UPower pil, MPRIS medya açılır penceresi, ekran parlaklığı OSD'si, 4 tema önayarı ve ayarlar penceresi. |

---

## KDE/KWin-Yerel Yapan Nedir?

Çoğu Quickshell, AGS ve Waybar masaüstü paketi `wlroots` veya bağımsız döşemeli pencere yöneticilerini (`hyprctl`, `niri msg`, `swaymsg`) hedefler ve `zwlr_foreign_toplevel_manager_v1` ya da `wlr-data-control` gibi ortama özel protokollere dayanır. Bunları bir KDE Plasma Wayland oturumunda çalıştırmak genellikle bozuk çalışma alanı araçlarına, eksik görev çubuğu durumuna veya çakışan bildirim arka plan programlarına yol açar.

**quickshell-kde**, doğrudan KDE Plasma 6 ve KWin 6 arayüzleri etrafında özel olarak tasarlanmıştır:

* **KWin Sanal Masaüstleri (`org.kde.KWin /VirtualDesktopManager`)**: D-Bus sinyalleri ve gecikmeli geri dönüş doğrulaması ile senkronize edilen olay güdümlü masaüstü geçişi, oluşturma, kaldırma ve fare tekerleğiyle geçiş döngüsü.
* **KWin Pencere Keşfi ve Meta Veri Önbelleği (`org.kde.KWin /WindowsRunner` ve `getWindowInfo`)**: Açık Wayland pencerelerini değişmez KWin UUID'si ile izler, gereksiz D-Bus süreç başlatmalarını önlemek için UUID başına `desktopFile` ve `resourceClass` meta verilerini önbelleğe alır ve pencere başlıklarından uygulama kimliği tahmin etmeye asla kalkışmadan `StartupWMClass`, `Exec` ve ters-DNS takma adları üzerinden masaüstü girişlerini çözümler.
* **UUID-Kesin Yerel Pencere Eylemleri (`org.kde.kwin.Scripting`)**: Tek pencereli küçültme/geri yükleme geçişi, çok pencereli aktif küçültme, zarif istemci kapatma (`win.closeWindow()`) ve çoklu monitör taşıma (`workspace.sendClientToScreen()`) için kesin pencere UUID'lerini hedefleyen geçici, kendi kendini bellekten kaldıran KWin 6 JavaScript çalışma alanı eylemleri yürütür. Yerel durum, KWin değişikliği onaylamadan önce asla iyimser biçimde değiştirilmez.
* **KDE Ekran Parlaklığı ve Yerel OSD Delegasyonu (`org.kde.ScreenBrightness` ve `org.kde.osdService`)**: KDE PowerDevil D-Bus API'leri aracılığıyla ekran başına donanım arka ışığını ayarlar (salt okunur `/sys/class/backlight` geri dönüşü ile) ve ana ses OSD geri bildirimini Plasma'nın yerel `osdService` bileşenine devrederken ekran parlaklığı için özel bir OSD sunar.
* **KDE Sistem Ayarları Entegrasyonu (`kcmshell6`)**: Bar modülleri (`clock`, `network`, `battery`, `audio`, `brightness`), canlı aktif süreç vurgusuyla tek örnekli KDE Kontrol Modüllerini (`kcm_clock`, `kcm_networkmanagement`, `kcm_powerdevilprofilesconfig`, `kcm_pulseaudio`, `kcm_kscreen`) açar veya durumunu değiştirir.
* **KWin Donanım Arka Plan Bulanıklığı (`ext_background_effect_manager_v1`)**: Yüzen yüzeylerin arkasında yerel KWin bulanıklığı istemek için Quickshell'in `BackgroundEffect.blurRegion` özelliğini kullanır.
* **Plasma Arka Plan Hizmetleriyle Sorunsuz Birlikte Çalışma**: Dahili `org.freedesktop.Notifications` sunucusu isteğe bağlıdır (varsayılan olarak `notificationsEnabled: false`), bu sayede açıkça etkinleştirilmediği sürece KDE Plasma'nın bildirim arka plan programıyla asla çakışmaz.

---

## Ekran Görüntüleri ve Görsel Vitrin

> [!NOTE]
> Depo ekran görüntüleri, Milestone 3A (`feat/composable-shell-ux`) arayüzünün canlı masaüstü oturumunda kaydedilmesini beklemektedir. Proje belgelendirme standartları uyarınca hiçbir yapay taslak veya sentetik yer tutucu kullanılmaz.
>
> Geliştiriciler ve katkıda bulunanlar: Gerekli görünümler, çözünürlükler ve GitHub depo yapılandırması için [Ekran Görüntüsü Kontrol Listesi ve Depo Kılavuzuna](docs/MAINTAINER.md) bakabilirler.

---

## Öne Çıkan Özellikler ve Doğrulama Durumu

Aşağıdaki yetenekler, depo test paketindeki doğrulama düzeylerine göre kategorize edilmiştir (`tests/test_milestone_3a.py` ve `tests/test_runtime_ux.py`):

| Alt Sistem | Yetenek | Dal (Branch) | Durum | Doğrulama Notları |
| :--- | :--- | :--- | :--- | :--- |
| **Birleştirilebilir Bar** | 4 kenar yerleşimi (`top`/`bottom`/`left`/`right`), yüzen veya yapışık, yapılandırılabilir yükseklik, opaklık, bulanıklık ve `ModuleRegistry` ile `left`/`center`/`right` modül yuvaları | `feat/composable-shell-ux` | **Uygulandı (Doğrulandı)** | `qmllint` ve otomatik testlerle doğrulandı (`test_02`, `test_06`, `test_09`). |
| **Dinamik Dock** | 4 kenar yerleşimi, üzerine gelince büyüme, gerçek otomatik gizleme (`revealDelay`/`hideDelay`), kesintisiz giriş maskesi, çalışan göstergeleri ve sabitlenmemiş çalışan uygulamalar | `feat/composable-shell-ux` | **Uygulandı (Doğrulandı)** | Geometri, otomatik gizleme durum makinesi ve gezinme kararlılığı doğrulandı (`test_04`, `tst_dock_autohide.qml`). |
| **KWin Pencere Kimliği** | Değişmez UUID takibi, önbelleğe alınan `getWindowInfo` D-Bus meta verileri, masaüstü girdisi eşleme (`StartupWMClass`/`Exec`/takma adlar), yüklü olmayan sabitlenmiş uygulama filtreleme | `feat/composable-shell-ux` | **Uygulandı (Doğrulandı)** | Başlık sahteciliğine, başlıksız pencerelere ve önbellek yeniden deneme sınırlarına karşı doğrulandı (`test_11`, `test_12`). |
| **KWin Pencere Eylemleri** | Pencere UUID'si ile odaklama, tek/çoklu pencere küçültme geçişi, zarif kapatma (`closeWindow`) ve çoklu çıkışa taşıma (`sendClientToScreen`) | `feat/composable-shell-ux` | **Uygulandı (Doğrulandı / Arayüz Kısmi)** | Durum güvenliği, reddedilen kapatma/taşıma mutabakatı ve KWin betik üretimi doğrulandı (`test_13`); fiziksel çoklu monitör pencere taşıma işlemi manuel çift ekran kontrolü gerektirir. |
| **Sistem Çekmecesi ve Taşma** | Freedesktop SNI entegrasyonu, öğe bazlı görünürlük politikaları (`auto`, `always`, `hidden`), `_status_icon_N` çakışma yönetimi, taşma oku ve açılır penceresi | `feat/composable-shell-ux` | **Uygulandı (Doğrulandı / Arayüz Kısmi)** | Politika kalıcılığı, durum geçişleri ve kimlik çakışma geçişleri doğrulandı (`test_10`); üçüncü taraf SNI menülerindeki canlı Wayland işaretçi yakalamaları manuel tıklama doğrulaması gerektirir. |
| **Bağlamsal Açılır Pencereler** | Dışlama kuralları ve Escape/dışarı tıklama ile kapanma özellikli `AnchoredPopup` açılır pencereleri (`AudioPopup`, `BrightnessPopup`, `MediaPopup`, `PowerPopup`, `DockMenu`, `WindowChooserPopup`) | `feat/composable-shell-ux` | **Uygulandı (Doğrulandı)** | Çıpa kenarları, açılır pencere dışlama kuralları ve KWin katman istifleme doğrulandı (`test_05`, `test_07`, `test_runtime_ux.py`). |
| **Ses ve Parlaklık** | PipeWire çıkış/giriş kontrolleri + KDE yerel ses OSD delegasyonu; `org.kde.ScreenBrightness` ekran başına arka ışık kontrolü + özel `BrightnessOSD` | `feat/composable-shell-ux` | **Uygulandı (Doğrulandı)** | Servis durumu, sysfs geri dönüşü ve OSD tetikleyicileri çalışma zamanı testlerinde doğrulandı. |
| **Ağ ve Pil** | Olay güdümlü `Quickshell.Networking` durumu (Wi-Fi SSID/sinyal gücü, Ethernet) ve `UPower` + `/sys/class/power_supply` pil durumu (`Charging`/`Full`/`Discharging`) | `feat/composable-shell-ux` | **Uygulandı (Doğrulandı)** | Bildirimsel bağlar ve pilin `Full` ile `Charging` ayrımı geri dönüşü doğrulandı. |
| **Uygulama Başlatıcı** | Bloklamayan Python XDG indeksleyicisi (`scan_apps.py`), kategori filtreleme ve güvenli parametrelendirilmiş başlatma özellikli Spotlight katmanı (`LauncherWindow`) | `main` ve `feat/composable-shell-ux` | **Uygulandı (Doğrulandı)** | İndekslenmiş arama, başlatma argümanı güvenliği ve ekran sahipliği doğrulandı. |
| **Temalandırma ve Ayarlar Arayüzü** | Canlı tema değişimi (*Breeze Dark*, *Catppuccin Mocha*, *Nord*, *Tokyo Night*) ve yüzey, monitör ile çekmece politikası yönetimi için grafiksel `SettingsWindow` | `feat/composable-shell-ux` | **Uygulandı (Doğrulandı)** | Yapılandırma kalıcılığı, Milestone 2'den geçiş ve dar/normal düzen doğrulandı (`test_03`, `test_08`, `test_10`). |
| **Çoklu Monitör Filtreleme** | Ekranlar ayrıldığında kilitlenmeyi önleme korumalı yüzey başına monitör seçimi (`"all"` veya açık çıkış listesi) | `main` ve `feat/composable-shell-ux` | **Kod Tamamlandı (Fiziksel Çoklu Monitör Doğrulanmadı)** | Filtreleme mantığı ve geri dönüş kuralları sentetik çoklu ekran testlerinde doğrulandı (`test_08`); fiziksel donanım takıp çıkarma işlemi başsız (headless) CI ortamında doğrulanmamıştır. |
| **Bildirim Kutuları (Toast)** | Dahili `org.freedesktop.Notifications` sunucusu ve `ToastHost` katmanı | `main` ve `feat/composable-shell-ux` | **İsteğe Bağlı (varsayılan: `false`)** | KDE Plasma'nın yerel bildirim hizmetiyle çakışmayı önlemek için varsayılan olarak devre dışıdır. |
| **Dinamik Duvar Kâğıdı Paletleri ve Düzen Önayarları** | Otomatik Material You / duvar kâğıdı renk çıkarımı ve tek tıklamayla düzen önayarları | *Planlandı* | **Planlandı (Yol Haritası)** | Milestone 3B/3C için planlanmıştır. |

---

## Neden `quickshell-kde` Seçilmeli?

1. **KDE Plasma 6 ve KWin Wayland'da Kalın**: Standart panelleri modern bir Quickshell arayüzü ile değiştirirken veya tamamlarken KDE'nin ekran yönetimini, kesirli ölçeklemesini, HDR/renk yönetimini, Polkit aracısını, KWallet'ını, XDG portallarını ve donanım uyumluluğunu koruyun.
2. **Birleştirilebilir ve Bildirimsel**: Modülleri (`launcher`, `workspaces`, `clock`, `media`, `tray`, `network`, `battery`, `audio`, `brightness`, `power`) JSON veya ayarlar arayüzü üzerinden `left`, `center` ve `right` yuvalarına taşıyın; Bar veya Dock'u herhangi bir ekran kenarına bağımsız olarak konumlandırın.
3. **Sıfır Sistem Müdahalesi**: Tamamen kullanıcı alanında çalışır (`quickshell -p ./shell.qml`). `/etc`, `fstab`, root yetkilerine veya mevcut `~/.config/plasma*` dosyalarınıza asla dokunmaz.
4. **Temiz Katman (Layer-Shell) Disiplini**: Tüm barlar, dock'lar, başlatıcılar ve ayar pencereleri `WlrLayer.Top` katmanında çalışır; Spectacle dikdörtgen ekran görüntüsü seçimi ve ekran kilitleyiciler için `WlrLayer.Overlay` katmanını tamamen engelsiz bırakır.

---

## Ekosistem Karşılaştırması

> *Araştırma ve kaynak doğrulama tarihi: **17 Ekim 2026**. Aşağıdaki karşılaştırma, her projenin resmi deposu ve belgelerinden alınan kamuya açık mimarileri ve hedef bileştiricileri yansıtmaktadır.*

| Proje | Birincil Hedef Bileştiriciler | Arayüz Araç Seti / Yığın | KDE Plasma 6 / KWin Wayland Desteği | Kapsam ve Ödünleşimler |
| :--- | :--- | :--- | :--- | :--- |
| **quickshell-kde** *(Bu Proje)* | **KDE Plasma 6 (KWin Wayland)** | Quickshell (Qt6 / QML) + Python XDG tarayıcı + KWin D-Bus / JS betikleri | **Amaca Özel Tasarım**: Yerel KWin `/VirtualDesktopManager`, `/WindowsRunner`, `getWindowInfo`, `org.kde.ScreenBrightness`, `kcmshell6` ve KWin 6 betikleme. | Bir KDE Plasma oturumu içindeki birleştirilebilir Bar, Dock, Başlatıcı, Açılır Pencereler, OSD ve Ayarlar üzerine odaklanır. KDE'nin ekran kilitleyicisinin, Polkit aracısının veya ekran arka plan programının yerini almaz. |
| [**KDE Plasma Yerel Panelleri**](https://invent.kde.org/plasma/plasma-workspace) (`plasma-workspace`) | **KDE Plasma 6 (KWin Wayland ve X11)** | Qt6 / QML, Kirigami, C++ Plasma Çatıları (`plasmashell`) | **Birincil Referans**: Harici layer-shell istemcilerine kapalı olan dahili bileştirici protokollerini (`org_kde_plasma_surface`, `KWin::ThumbnailItem`) kullanır. | Canlı pencere küçük resimleri, araçlar (Plasmoidler) ve tam Alt+Tab/Masaüstünü Göster panel kalıcılığına sahip eksiksiz masaüstü ortamı; ancak `plasmashell` yapısına sıkı sıkıya bağlıdır. |
| [**Noctalia**](https://github.com/noctalia-dev/noctalia) ([Belgeler](https://docs.noctalia.dev)) | Hyprland, Niri, Sway, Labwc, MangoWC, Scroll, **KDE Plasma** | Özel Wayland + OpenGL ES kabuğu (mevcut ana hatta Qt/GTK bağımlılığı yoktur; eski v4 Quickshell kullanıyordu) | **Belgelenmiş Destek (Birincil Olmayan)**: Resmi olarak KDE Plasma ayarlarını belgeler ([KDE Belgeleri](https://docs.noctalia.dev/noctalia/compositor-settings/kde/)). Barlar, dock, OSD, başlatıcı, kontrol merkezi, çalışma alanları (`org_kde_plasma_virtual_desktop`), görev çubuğu (`KWin` betik köprüsü) ve sistem çekmecesi layer-shell ile çalışır; `wlroots` protokolleri gerektiren özellikler (pano geçmişi, otomatik yapıştırma, ekran görüntüleri, kilit ekranı arka planı ve gece ışığı) standart KWin'de kullanılamaz. | Bar, dock, başlatıcı, kilit ekranı, duvar kâğıdı arka plan programı, kontrol merkezi ve masaüstü widget'larını içeren kapsamlı bağımsız Wayland kabuğu. |
| [**DankMaterialShell**](https://github.com/AvengeMedia/DankMaterialShell) ([Belgeler](https://danklinux.com/docs)) | **Niri, Hyprland, Sway**, MangoWC, labwc, Scroll, Miracle WM | Quickshell (QtQuick/QML) + Go arka ucu (`dms` CLI) | **Hedeflenmiyor**: KWin/Plasma ortamı yerine bağımsız Wayland bileştiricilerinde `waybar`, `swaylock`, `swayidle`, `mako`, `fuzzel` ve `polkit` bileşenlerinin yerini almak üzere tasarlanmıştır. | Go sistem arka plan programları, dinamik duvar kâğıdı temalandırması (`matugen`), kilit ekranı ve dağıtım paketlemesi içeren eksiksiz Material 3 masaüstü paketi. |
| [**Caelestia Shell**](https://github.com/caelestia-dots/shell) | **Hyprland** | Quickshell (`quickshell-git`) + C++/CMake QML eklentileri + `caelestia-cli` | **Ana Depoda Hedeflenmiyor**: `hyprctl` IPC ve Hyprland küresel kısayollarına dayanır (KDE için ayrı üçüncü taraf topluluk uyarlamaları mevcuttur). | Caelestia Hyprland yapılandırma dosyaları, Cava ses görselleştiricisi ve Material 3 şekilleri ile sıkı bir şekilde entegre edilmiş akıcı kabuk. |
| [**HyprPanel**](https://github.com/Jas-SinghFSU/HyprPanel) | **Hyprland** | Astal / AGS (GTK3, GJS/TypeScript) | **Desteklenmiyor**: Açıkça Hyprland IPC soketlerine, çalışma alanlarına ve istemci durumuna bağımlıdır. | Zengin özellikli Hyprland barı/paneli; geliştirme süreci [Wayle](https://github.com/wayle-rs/wayle) (Rust/GTK4) projesine aktarıldığı için şu anda bakım modundadır. |

---

## Temel Avantajlar ve Mevcut Sınırlamalar

### Temel Avantajlar
* **Bileştirici Yalıtım Katmanı**: `modules/` içindeki arayüz modülleri hiçbir zaman doğrudan kabuk komutları veya `qdbus6` çağrıları yürütmez; tüm KWin etkileşimleri `KWinService` ve `WindowService` üzerinden geçer.
* **İyimser Olmayan Pencere Eylemi Güvenliği**: Dock üzerinden pencere kapatma veya monitör taşıma isteğinde bulunmak, yerel durumu hiçbir zaman vaktinden önce değiştirmez. Bir uygulama "Kaydedilmemiş Değişiklikler" uyarısı gösterirse veya kapatma isteğini reddederse, dock göstergesi KWin'in `/WindowsRunner` listesi pencerenin kapandığını onaylayana kadar doğru kalır.
* **Dayanıklı Sistem Çekmecesi Kimliği**: Öğe bazlı çekmece politikaları (`auto`, `always`, `hidden`), tek bir örnek mevcut olduğunda Chromium/Electron `_status_icon_N` soneklerini normalleştirir ve aynı uygulamanın birden fazla örneği aynı anda kaydolduğunda otomatik olarak ayrım yaparak kayıtlı kullanıcı tercihlerini yeniden başlatmalar arasında korur.
* **Hızlı, Düşük Yüklü Pencere Taraması**: `WindowService`, KWin `getWindowInfo` meta verilerini değişmez pencere UUID'si başına önbelleğe alır; bu sayede kararlı durumdaki 1000 ms'lik taramalar, pencere başına D-Bus süreç fırtınası veya sınırsız yeniden deneme döngüsü olmadan yalnızca tek bir `/WindowsRunner` sorgusu yürütür.

### Mevcut Sınırlamalar (Doğrulanmış Yetenekler)
* **Dock'ta Canlı Pencere Önizleme Küçük Resimleri Yok**: KWin Wayland, canlı pencere dokuları için ayrıcalıksız bir genel Wayland protokolü sunmaz (`zwlr_screencopy_v1` wlroots'a özgüdür ve PipeWire ekran yayını pencere başına etkileşimli izin iletişim kutuları tetikler). Birden fazla açık penceresi olan bir uygulamaya tıklandığında, sahte küçük resimler yerine doğru pencere başlıklarını, simgelerini ve etkinleştirme / yeni pencere eylemlerini gösteren `WindowChooserPopup` açılır (pencere başına Kapatma ve Ekrana Taşıma eylemleri `DockMenu` sağ tık bağlam menüsünde mevcuttur).
* **`Alt+Tab` ve `Masaüstünü Göster` Sırasında Yüzen Yüzey Davranışı**: `reserveSpace: false` (`exclusiveZone: 0`) olduğunda, KWin'in tam ekran `TabBox` (`Alt+Tab`) ve `ShowDesktop` (`Meta+D`) efektleri, yer ayırmamış `WlrLayer.Top` layer-shell pencerelerini yüzen yüzeyler olarak ele alır ve geçici olarak gizler veya örter. Panelleri `WlrLayer.Overlay` katmanına taşımak, ekran kilitleyicilerin ve Spectacle ekran görüntüsü seçicilerinin üzerinde render edileceği gerekçesiyle bilinçli olarak reddedilmiştir. Kalıcı panel boşluğu tercih eden kullanıcılar `reserveSpace: true` ayarını etkinleştirebilir.
* **Pencere Listeleme İçin Düzenli Sorgulama (Polling) Geri Dönüşü**: Standart KWin Wayland, harici istemcilerin `zwlr_foreign_toplevel_manager_v1` protokolüne bağlanmasını kısıtladığı için pencere listesi senkronizasyonu 1000 ms'lik bir `/WindowsRunner` D-Bus sorgusu kullanır (dock pencere eylemlerinden hemen sonra 180 ms'lik anlık mutabakat ile desteklenir).
* **Manuel Çoklu Monitör ve Yerel Menü Yakalama Doğrulaması**: Çoklu monitör filtreleme ve açılır pencere koordinat eşleme otomatik QML birim testleriyle kapsansa da, fiziksel çoklu monitör donanım takıp çıkarma ve gerçek fare ile Wayland yerel menü yakalamaları (`QsWindow` / SNI `DbusMenu`) canlı bir masaüstü oturumunda etkileşimli olarak doğrulanmalıdır.

---

## Mimari Genel Bakış

```
┌──────────────────────────────────────────────────────────────────────┐
│                           Arayüz Sunumu                              │
│  modules/bar · modules/dock · modules/launcher · modules/settings    │
│  modules/media · modules/osd · modules/notifications                 │
│  components/ (AnchoredPopup, Surface, IconButton, Slider, Tooltip)   │
└──────────────────────────────────┬───────────────────────────────────┘
                                   │ Bildirimsel QML Bağları ve Sinyalleri
┌──────────────────────────────────▼───────────────────────────────────┐
│                         Singleton Servisler                          │
│  KWinService · WindowService · ConfigService · ThemeService          │
│  ApplicationService · AudioService · BrightnessService · MprisService│
│  NetworkService · PowerService · NotificationService · ModuleRegistry│
└────────────────┬───────────────────────────────────┬─────────────────┘
                 │ D-Bus / KWin Betikleri / Wayland  │ Yerel JSON / XDG
┌────────────────▼─────────────────┐ ┌───────────────▼─────────────────┐
│      KDE Plasma 6 / KWin 6       │ │    Quickshell ve Sistem API'leri│
│  /VirtualDesktopManager, /KWin,  │ │  PipeWire, UPower, Mpris, SNI,  │
│  /WindowsRunner, ScreenBrightness│ │  Quickshell.Networking, JSON    │
└──────────────────────────────────┘ └─────────────────────────────────┘
```

### Depo Yapısı

```text
quickshell-kde/
├── shell.qml                                # Ana Quickshell giriş noktası
├── components/                              # Yeniden kullanılabilir arayüz bileşenleri
│   ├── AnchoredPopup.qml                    # Kenara duyarlı Wayland PopupWindow temeli
│   ├── Badge.qml                            # Sayı/durum hap göstergesi
│   ├── Card.qml                             # Yapılandırılmış içerik kapsayıcısı
│   ├── IconButton.qml                       # Vurgu/dalgalanma/ipucu özellikli düğme
│   ├── Slider.qml                           # Tıklama/sürükleme/tekerlek değer kaydırıcısı
│   ├── Surface.qml                          # KWin bulanıklık destekli tema kapsayıcısı
│   ├── SvgIcon.qml                          # Freedesktop teması ve SVG simge yükleyicisi
│   ├── Tooltip.qml                          # PopupWindow tabanlı gezinme araç ipucu
│   └── qmldir
├── modules/                                 # Birleştirilebilir kabuk yüzeyleri ve menüler
│   ├── bar/                                 # Bar yüzeyi, yuva modülleri ve açılır pencereler
│   │   ├── Bar.qml
│   │   ├── AudioModule.qml & AudioPopup.qml
│   │   ├── BrightnessModule.qml & BrightnessPopup.qml
│   │   ├── ClockModule.qml, LauncherButton.qml, MediaModule.qml
│   │   ├── NetworkModule.qml, BatteryModule.qml, WorkspacesModule.qml
│   │   ├── PowerButton.qml & PowerPopup.qml
│   │   └── TrayModule.qml                   # Görünürlük politikaları ve taşma özellikli SNI
│   ├── dock/                                # Yüzen/yapışık Dock ve pencere kontrolleri
│   │   ├── Dock.qml, DockItem.qml, DockSeparator.qml
│   │   ├── DockMenu.qml                     # Odaklan, Ekrana Taşı, Kapat menüsü
│   │   └── WindowChooserPopup.qml           # Çoklu pencere seçici açılır penceresi
│   ├── launcher/                            # Tam ekran Spotlight uygulama başlatıcısı
│   ├── media/                               # Genişletilmiş MPRIS medya oynatıcı penceresi
│   ├── notifications/                       # İsteğe bağlı Freedesktop bildirim kutuları
│   ├── osd/                                 # Ekran parlaklığı ekran üstü göstergesi (HUD)
│   └── settings/                            # Canlı grafiksel ayarlar penceresi
├── services/                                # Singleton iş mantığı ve bileştirici bağdaştırıcıları
│   ├── applications/                        # XDG masaüstü tarayıcısı (scan_apps.py) ve başlatıcı
│   ├── audio/                               # PipeWire ses + KDE yerel OSD tetikleyicisi
│   ├── battery/                             # UPower ve sysfs güç durumu servisi
│   ├── brightness/                          # KDE ScreenBrightness D-Bus + sysfs servisi
│   ├── config/                              # Kalıcı JSON yapılandırması ve şema geçişi
│   ├── core/                                # JsonStore, Log.js ve ModuleRegistry
│   ├── kwin/                                # KWinService, WindowService ve KWin JS betikleri
│   ├── mpris/                               # Aktif medya oynatıcı kontrolcüsü
│   ├── network/                             # Bildirimsel Quickshell.Networking servisi
│   ├── notifications/                       # Koşullu NotificationServer yükleyicisi
│   └── theme/                               # Tasarım belirteçleri ve canlı tema motoru
├── themes/                                  # Dahili JSON renk temaları
│   ├── breeze-dark.json
│   ├── catppuccin-mocha.json
│   ├── nord.json
│   └── tokyo-night.json
├── config/                                  # Varsayılan geri dönüş yapılandırmaları
│   ├── bar_config.json
│   ├── dock_config.json
│   └── theme_config.json
├── tests/                                   # Otomatik QML lint, birim ve çalışma zamanı testleri
│   ├── test_milestone_3a.py
│   ├── test_runtime_ux.py
│   └── tst_dock_autohide.qml
└── docs/                                    # Mimari ve alt sistem belgeleri
```

---

## Test Edilen Platformlar ve Bağımlılıklar

### Doğrulanmış Referans Ortamı
* **İşletim Sistemi**: Arch Linux (`x86_64`, rolling)
* **Masaüstü / Bileştirici**: KDE Plasma `6.7.5` / KWin Wayland (`kwin_wayland 6.7.5`)
* **Kabuk Sunucusu**: Quickshell `0.3.2` (`>= 0.3.0` gereklidir)
* **Qt / Python**: Qt6 (`qdbus6`, `qmllint`, `qmltestrunner`) / Python `3.14` (`>= 3.9` gereklidir)

### Çalışma Zamanı Bağımlılıkları

| Bileşen | Paket / İkili (Arch Linux) | Rol | Gereksinim |
| :--- | :--- | :--- | :--- |
| **Quickshell** | `quickshell` (`>= 0.3.0`) | Wayland layer-shell QML sunucusu ve yerel servis bağları | **Zorunlu** |
| **KWin Wayland** | `kwin` / `plasma-workspace` | Bileştirici, `/VirtualDesktopManager`, `/WindowsRunner`, KWin Betikleme | **Zorunlu** |
| **Qt6 D-Bus Araçları** | `qt6-tools` (`qdbus6`) | KWin çalışma alanı, pencere meta verileri ve parlaklık sorguları için D-Bus IPC | **Zorunlu** |
| **Python 3** | `python` (`>= 3.9`) | Bloklamayan XDG `.desktop` girdi ayrıştırıcısı (`scan_apps.py`) | **Zorunlu** |
| **PipeWire** | `pipewire` / `pipewire-pulse` | Ses giriş/çıkış ses düzeyi ve sessize alma entegrasyonu | **Zorunlu** |
| **KDE CLI Araçları** | `kde-cli-tools` (`kcmshell6`, `kioclient`) | KDE Kontrol Modüllerini (KCM) ve `.desktop` dosyalarını başlatma | **Önerilen** |
| **UPower** | `upower` | Pil yüzdesi ve AC güç durumu izleme | **Önerilen** (Dizüstü) |
| **NetworkManager** | `networkmanager` | `Quickshell.Networking` üzerinden ağ bağlantı durumu | **Önerilen** |

### Geliştirme ve Test Bağımlılıkları
* `qt6-declarative` (`qmllint`, `qmlformat`, `qmltestrunner`)
* `python3` (`tests/test_milestone_3a.py` ve `tests/test_runtime_ux.py` için `unittest` çalıştırıcısı)

---

## Hızlı Başlangıç

**quickshell-kde**'yi yerel bir klondan çalıştırmak tamamen yalıtılmıştır—varsayılanları `./config/` dizininden okur, kullanıcı ayarlarını yalnızca `~/.config/quickshell-kde/` dizininde saklar ve KDE Plasma yapılandırmanızı asla değiştirmez.

### 1. Klonlayın ve Dalı Seçin

```bash
git clone https://github.com/SnTR370/quickshell-kde.git
cd quickshell-kde

# Önerilen: Aktif Milestone 3A birleştirilebilir kabuk dalına geçin
git checkout feat/composable-shell-ux

# Veya Milestone 2 temel sürümü için 'main' dalında kalın
```

### 2. Kabuğu Yalıtılmış Modda Çalıştırın

```bash
quickshell -p ./shell.qml
```

Çalışan kabuk örneğini istediğiniz zaman durdurmak için:

```bash
quickshell kill
```

### 3. Kod Denetimi (Lint) ve Otomatik Doğrulama Testlerini Çalıştırın

```bash
# Milestone 3A test paketini çalıştırın (tüm QML dosyalarında qmllint + 13 alt sistem testi içerir)
python3 -m unittest tests/test_milestone_3a.py -v

# Çalışma zamanı kullanıcı deneyimi regresyon test paketini çalıştırın (7 test)
python3 -m unittest tests/test_runtime_ux.py -v
```

---

## Yapılandırma ve Özelleştirme

Kullanıcı yapılandırma dosyaları `~/.config/quickshell-kde/` dizininde saklanır ve mevcut olmadığında otomatik olarak [`config/`](config/) dizinine başvurulur. Çoğu ayar, kabuk içindeki **Ayarlar Paneli** üzerinden canlı olarak ayarlanabilir (Uygulama Başlatıcıdan veya Bar üzerinden erişilebilir).

### Birleştirilebilir Bar (`~/.config/quickshell-kde/bar_config.json`)

```json
{
  "enabled": true,
  "floating": true,
  "edge": "top",
  "edgeOffset": 8,
  "reserveSpace": false,
  "height": 30,
  "left": ["launcher", "workspaces"],
  "center": ["clock"],
  "right": ["media", "tray", "network", "battery", "audio", "brightness", "power"],
  "opacity": 0.92,
  "monitors": "all",
  "blur": true,
  "notificationsEnabled": false,
  "trayPolicies": {
    "discord": "always",
    "nm-applet": "hidden"
  }
}
```

* **Yuva Modülleri**: Kayıtlı herhangi bir modül kimliğini (`launcher`, `workspaces`, `clock`, `media`, `tray`, `network`, `battery`, `audio`, `brightness`, `power`) `left`, `center` veya `right` yuvalarına yerleştirin.
* **Yüzey Geometrisi**: `edge` (`"top"`, `"bottom"`, `"left"`, `"right"`), `floating` (`true`/`false`) ve `reserveSpace` (tam ekran uygulamaların sınır tanımaması için `false`, ekranda ayrılmış alan tutmak için `true`) değerlerini ayarlayın.
* **Sistem Çekmecesi Politikaları (`trayPolicies`)**: `"auto"` (SNI `Active`/`NeedsAttention` ile `Passive` durumunu izler), `"always"` (barda her zaman gösterilir) ve `"hidden"` (çekmece taşma açılır penceresine taşınır) değerlerini destekleyen öğe bazlı görünürlük haritası.

### Dinamik Dock (`~/.config/quickshell-kde/dock_config.json`)

```json
{
  "enabled": true,
  "floating": true,
  "edge": "bottom",
  "edgeOffset": 8,
  "reserveSpace": false,
  "iconSize": 44,
  "autoHide": false,
  "hideDelay": 350,
  "revealDelay": 120,
  "monitors": "all",
  "pinned": [
    "org.kde.dolphin",
    "org.kde.konsole",
    "firefox",
    "code",
    "systemsettings"
  ]
}
```

### Tema Önayarları (`~/.config/quickshell-kde/theme_config.json`)

Temaları Ayarlar arayüzünden canlı olarak veya `theme_config.json` içindeki `activeTheme` anahtarıyla değiştirin:
* `breeze-dark` *(Varsayılan — KDE Breeze Dark ile uyumludur)*
* `catppuccin-mocha`
* `nord`
* `tokyo-night`

---

## Geliştirme Durumu ve Yol Haritası

* [x] **Milestone 1 — KWin Temeli**: Yalıtılmış `KWinService` bağdaştırıcısı, sanal masaüstleri, XDG uygulama tarayıcısı, PipeWire ses, UPower pil, MPRIS medya ve tema motoru.
* [x] **Milestone 2 — Kabuk Deneyimi (`main`)**: Dock otomatik gizleme ve büyütme, ekran parlaklığı servisi ve OSD, monitör bazlı filtreleme, KWin donanım bulanıklığı ve Ayarlar arayüzü.
* [x] **Milestone 3A — Birleştirilebilir Kabuk Deneyimi (`feat/composable-shell-ux`)**:
  * [x] Sıfır-strut yüzen varsayılanlara sahip 4 kenarlı birleştirilebilir Bar ve Dock yüzey geometrisi
  * [x] `ModuleRegistry` yuva tabanlı modül yerleşimi ve otomatik Milestone 2 yapılandırma geçişi
  * [x] `AnchoredPopup` bağlamsal açılır pencereleri (`AudioPopup`, `BrightnessPopup`, `MediaPopup`, `PowerPopup`, `WindowChooserPopup`)
  * [x] Sistem çekmecesi öğe bazlı görünürlük politikaları (`auto`/`always`/`hidden`), taşma penceresi ve `_status_icon_N` çakışma güvenliği
  * [x] Deterministik KWin pencere kimliği çözümleme ve önbelleğe alınan `getWindowInfo` meta verileri
  * [x] İyimser olmayan durum mutabakatı ile UUID hedefli KWin 6 pencere eylemleri (etkinleştirme, küçültme geçişi, zarif kapatma, ekrana taşıma)
* [ ] **Milestone 3B / 3C — Planlanan**:
  * [ ] Düzen önayarları (macOS tarzı yüzen dock, klasik KDE/Windows paneli, minimalist üst bar)
  * [ ] Dinamik duvar kâğıdı renk çıkarımı (Material You / `matugen` palet üretimi)
  * [ ] Otomatik `qmllint` ve başsız QML birim testleri için GitHub Actions CI iş akışı

---

## Belgeler

* [Birleştirilebilir Kabuk Kullanıcı Deneyimi Belirtimi (v1.0)](docs/UX_SPEC_V1.md) — Milestone 3A yüzey modeli, 4 kenar geometrisi, açılır pencere çıpalama ve KWin katman istifleme.
* [Sistem Mimarisi](docs/ARCHITECTURE.md) — Model-View-Service katmanlaması ve singleton veri akışı.
* [KWin Wayland Entegrasyonu](docs/KWIN_INTEGRATION.md) — D-Bus arayüzleri, KWin 6 betikleme, pencere küçük resmi protokol bulguları ve layer-shell davranışı.
* [Modül Referansı](docs/MODULES.md) — Yuva modülü tanımlayıcıları, etkileşimler ve bağlamsal açılır pencereler.
* [Yapılandırma Kılavuzu](docs/CONFIGURATION.md) — `bar_config.json`, `dock_config.json`, `theme_config.json` için tam JSON şeması ve geçiş kuralları.
* [Geliştirme Kılavuzu](DEVELOPMENT.md) — Servis sözleşmeleri, kodlama standartları ve doğrulama iş akışları.
* [Bakım ve Tanıtım Kılavuzu](docs/MAINTAINER.md) — Ekran görüntüsü alma kontrol listesi ve GitHub depo meta verileri.

---

## Katkıda Bulunma, Lisans ve Atıf

* **Katkıda Bulunma**: Çekme istekleri (PR) ve hata bildirimleri memnuniyetle karşılanır. Mimari kurallar (katı KWin servis yalıtımı, sıfır root betiği, sabit kodlanmış yolların bulunmaması) için lütfen [CONTRIBUTING.md](CONTRIBUTING.md) dosyasını inceleyin.
* **Lisans**: [MIT Lisansı](LICENSE) kapsamında yayımlanmıştır.
* **Atıf**: Esinlenilen açık kaynak projeleri ve uyarlanan mimari yaklaşımlar, tam telif hakkı ve lisans bildirimleriyle birlikte [ATTRIBUTION.md](ATTRIBUTION.md) dosyasında belgelenmiştir.
