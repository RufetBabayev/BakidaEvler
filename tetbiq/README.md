# BakıdaEvlər.az tətbiqi (Expo / React Native, yalnız Android)

Supabase-dəki elanları oxuyur: yeni satış elanları, ev sahibi / şübhəli / makler filtri, otaq, qiymət və rayon filtrləri. Elana toxunanda bina.az linki açılır.

## Telefonda sınamaq (Expo Go)

1. Telefona **Expo Go** tətbiqini quraşdırın (Play Store).
2. Kompüterdə:

   ```powershell
   cd C:\Users\Keke\Desktop\BakidaEvler\tetbiq
   npm install
   npx expo start
   ```

3. Telefon və kompüter eyni Wi-Fi-da olsun. Terminaldakı QR kodu Expo Go ilə oxudun.
4. Supabase-də yaratdığınız e-poçt və parolla daxil olun.

## Qeyd

- `src/config.ts`-dəki açar İCTİMAİ (publishable) açardır. Gizli `service_role`/`sb_secret` açarını buraya heç vaxt yazmayın.
- Oxuma icazəsi yalnız giriş etmiş istifadəçiyə verilib (`toplayici/schema.sql`-in sonu).
