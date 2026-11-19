# Toplayıcı (bina.az, Bakı, satış)

Bu proqram bina.az-dan Bakıdakı ən yeni satış elanlarını (mənzil və həyət evi) toplayır, mülkiyyətçi / vasitəçi kimi qeyd edir və nəticəni `data/` qovluğuna JSON faylı kimi yazır.

## Windows-da işə salmaq

1. **Python qurun** (bir dəfəlik): https://www.python.org/downloads/ ünvanından yükləyin. Quraşdırmada **"Add python.exe to PATH"** xanasını işarələyin.
2. **PowerShell** açın və qovluğa keçin:

   ```powershell
   cd C:\Users\Keke\Desktop\BakidaEvler\toplayici
   ```

3. **Kitabxananı qurun** (bir dəfəlik):

   ```powershell
   pip install -r requirements.txt
   ```

4. **İşə salın:**

   ```powershell
   python main.py
   ```

   Təxminən 2-3 dəqiqə çəkir (saytı yükləməmək üçün sorğular arasında 2-4 saniyə gözləyir).

## Necə işləyir

- **İlk dəfə** siyahıdan 75 elan götürür (təxminən 3 dəqiqə).
- **Sonrakı dəfələr** yalnız son işləmədən bəri yaranan yeni elanları yoxlayır (adətən bir neçə saniyə). Yeni elan yoxdursa fayl yazılmır.
- Sıfırdan başlamaq üçün `seen.json`-un içini `{}` edin, ya da `python main.py --siyahi` yazın.
- Hər elanda `makler_nəticə` var: `makler`, `ev sahibi` və ya `şübhəli makler` (mülkiyyətçi yazılıb, amma eyni telefonla 3+ elan).

## Nə alırsınız

- `data\bina_YYYY-MM-DD_HHMM.json` — toplanan elanlar.
- Konsolda xülasə, məsələn: `bina.az: 75 elan toplandı | 75 yeni | 20 mülkiyyətçi, 55 vasitəçi | 0 xəta`
- `seen.json` — görülmüş elanların siyahısı. İkinci dəfə işə salanda yalnız YENİ elanlar tam çəkilir və `"yeni": true` olur. Sıfırdan başlamaq istəsəniz faylın içini `{}` edin.

## Telefon nömrəsi

Saytda nömrə "Nömrəni göstər" düyməsinin arxasındadır. Defolt halda nömrə **maskalı** gəlir, məsələn `(077) 710-16-●●` (son 2 rəqəm gizli). Tam nömrə üçün:

```powershell
python main.py --telefon
```

Bu, hər YENİ elan üçün saytın düyməsinin göndərdiyi sorğunun eynisini göndərir (login/captcha yoxdur). Elan sahibinin "nömrə baxışı" statistikasında görünə bilər, ona görə yalnız lazım olanda işlədin.

## Problemlər

- `python tapılmadı`: Python-u yenidən qurun və "Add to PATH" xanasını işarələyin, sonra PowerShell-i bağlayıb yenidən açın.
- Konsolda `BLOKLANMA ƏLAMƏTİ` yazılırsa: proqram özü dayanır. Bir neçə saat gözləyin və mənə bildirin.
