import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator, AppState, FlatList, Linking, Pressable, RefreshControl, ScrollView, StyleSheet, Text, TextInput, View,
} from "react-native";
import { supabase } from "./supabase";
import { colors } from "./theme";
import { BOS_FILTR, Elan, Filtr, SAYTLAR, Satici } from "./types";

const SAHIFE = 30;

const SATICI: { id: Satici; ad: string }[] = [
  { id: "hamisi", ad: "Hamısı" },
  { id: "ev sahibi", ad: "Ev sahibi" },
  { id: "subheli", ad: "Şübhəli" },
  { id: "makler", ad: "Makler" },
  { id: "namelum", ad: "Naməlum" },
];

function nömrə(v: string): number | null {
  const n = parseInt(v.replace(/\D/g, ""), 10);
  return Number.isFinite(n) ? n : null;
}

function nəvaxt(iso: string): string {
  const d = (Date.now() - new Date(iso).getTime()) / 60000;
  if (d < 1) return "indicə";
  if (d < 60) return `${Math.floor(d)} dəq əvvəl`;
  if (d < 1440) return `${Math.floor(d / 60)} saat əvvəl`;
  return `${Math.floor(d / 1440)} gün əvvəl`;
}

function qiymət(e: Elan): string {
  if (e.qiymet == null) return "—";
  return `${Math.round(e.qiymet).toLocaleString("ru-RU")} ${e.valyuta ?? "AZN"}`;
}

function etiket(e: Elan): { text: string; color: string } {
  if (e.makler_netice === "ev sahibi") return { text: "Ev sahibi", color: colors.owner };
  if (e.makler_netice === "şübhəli makler") return { text: "Şübhəli makler", color: colors.suspect };
  if (e.makler_netice === "naməlum") return { text: "Naməlum", color: colors.muted };
  return { text: "Makler", color: colors.agent };
}

function Chip({ ad, aktiv, onPress }: { ad: string; aktiv: boolean; onPress: () => void }) {
  return (
    <Pressable onPress={onPress} style={[s.chip, aktiv && s.chipOn]}>
      <Text style={[s.chipText, aktiv && s.chipTextOn]}>{ad}</Text>
    </Pressable>
  );
}

export default function ListScreen() {
  const [filtr, setFiltr] = useState<Filtr>(BOS_FILTR);
  const [elanlar, setElanlar] = useState<Elan[]>([]);
  const [rayonlar, setRayonlar] = useState<string[]>([]);
  const [yuklenir, setYuklenir] = useState(true);
  const [yenilenir, setYenilenir] = useState(false);
  const [daha, setDaha] = useState(true);
  const [xeta, setXeta] = useState<string | null>(null);
  const [filtrAcik, setFiltrAcik] = useState(false);
  const sorgu = useRef(0); // köhnə cavabların yenisini əzməməsi üçün

  const yukle = useCallback(async (f: Filtr, offset: number) => {
    const id = ++sorgu.current;
    let q = supabase.from("elanlar").select("*").order("ilk_gorulme", { ascending: false }).range(offset, offset + SAHIFE - 1);
    if (f.satici === "ev sahibi") q = q.eq("makler_netice", "ev sahibi");
    if (f.satici === "subheli") q = q.eq("makler_netice", "şübhəli makler");
    if (f.satici === "makler") q = q.eq("makler_netice", "makler");
    if (f.satici === "namelum") q = q.eq("makler_netice", "naməlum");
    if (f.sayt) q = q.eq("menba", f.sayt);
    if (f.otaq != null) q = f.otaq >= 5 ? q.gte("otaq_sayi", 5) : q.eq("otaq_sayi", f.otaq);
    const min = nömrə(f.minQiymet), max = nömrə(f.maxQiymet);
    if (min != null) q = q.gte("qiymet", min);
    if (max != null) q = q.lte("qiymet", max);
    if (f.rayon) q = q.eq("rayon", f.rayon);
    const { data, error } = await q;
    if (id !== sorgu.current) return;
    if (error) {
      setXeta("Yükləmə alınmadı: " + error.message);
      return;
    }
    setXeta(null);
    const sıra = (data ?? []) as Elan[];
    setElanlar((köhnə) => (offset === 0 ? sıra : [...köhnə, ...sıra]));
    setDaha(sıra.length === SAHIFE);
  }, []);

  // filtr dəyişəndə yenidən yüklə
  useEffect(() => {
    setYuklenir(true);
    yukle(filtr, 0).finally(() => setYuklenir(false));
  }, [filtr, yukle]);

  // rayon siyahısı (bir dəfə)
  useEffect(() => {
    supabase.from("elanlar").select("rayon").not("rayon", "is", null).limit(1000).then(({ data }) => {
      const set = new Set((data ?? []).map((x: { rayon: string }) => x.rayon));
      setRayonlar([...set].sort((a, b) => a.localeCompare(b, "az")));
    });
  }, []);

  // tətbiqə hər qayıdanda (fonda idi, indi önə çıxdı) siyahı avtomatik yenilənir: bildirişə basıb girəndə də
  useEffect(() => {
    const sub = AppState.addEventListener("change", (state) => {
      if (state === "active") yukle(filtr, 0);
    });
    return () => sub.remove();
  }, [filtr, yukle]);

  async function yenile() {
    setYenilenir(true);
    await yukle(filtr, 0);
    setYenilenir(false);
  }

  function renderItem({ item: e }: { item: Elan }) {
    const t = etiket(e);
    const mert = e.data?.mərtəbə != null && e.data?.ümumi_mərtəbə != null ? `${e.data.mərtəbə}/${e.data.ümumi_mərtəbə} mərtəbə` : null;
    const xet = [e.otaq_sayi ? `${e.otaq_sayi} otaq` : null, e.sahe_m2 ? `${Math.round(e.sahe_m2)} m²` : null, mert].filter(Boolean).join(" · ");
    return (
      <Pressable style={s.card} onPress={() => e.link && Linking.openURL(e.link)}>
        <View style={s.row}>
          <Text style={s.price}>{qiymət(e)}</Text>
          <Text style={[s.badge, { backgroundColor: t.color }]}>{t.text}</Text>
        </View>
        <Text style={s.line}>{xet}</Text>
        <Text style={s.muted}>
          {[e.kateqoriya, e.rayon, e.metro].filter(Boolean).join(" · ")}
        </Text>
        <View style={s.row}>
          <Text style={s.muted}>
            {e.satici_adi ?? ""}{e.telefon ? ` · ${e.telefon}` : ""}
            {e.telefon_elan_sayi && e.telefon_elan_sayi > 1 ? ` (${e.telefon_elan_sayi} elan)` : ""}
          </Text>
          <Text style={s.time}>{e.menba} · {nəvaxt(e.ilk_gorulme)}</Text>
        </View>
      </Pressable>
    );
  }

  return (
    <View style={s.root}>
      <View style={s.bar}>
        <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chips}>
          {SATICI.map((x) => (
            <Chip key={x.id} ad={x.ad} aktiv={filtr.satici === x.id} onPress={() => setFiltr({ ...filtr, satici: x.id })} />
          ))}
        </ScrollView>
        <Pressable onPress={() => setFiltrAcik(!filtrAcik)} style={s.filtrBtn}>
          <Text style={s.filtrBtnText}>{filtrAcik ? "Bağla" : "Filtr"}</Text>
        </Pressable>
      </View>

      {filtrAcik && (
        <View style={s.panel}>
          <Text style={s.label}>Sayt</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chips}>
            <Chip ad="Hamısı" aktiv={filtr.sayt == null} onPress={() => setFiltr({ ...filtr, sayt: null })} />
            {SAYTLAR.map((x) => (
              <Chip key={x} ad={x} aktiv={filtr.sayt === x} onPress={() => setFiltr({ ...filtr, sayt: x })} />
            ))}
          </ScrollView>
          <Text style={s.label}>Otaq sayı</Text>
          <View style={s.chips}>
            <Chip ad="Hamısı" aktiv={filtr.otaq == null} onPress={() => setFiltr({ ...filtr, otaq: null })} />
            {[1, 2, 3, 4, 5].map((n) => (
              <Chip key={n} ad={n === 5 ? "5+" : String(n)} aktiv={filtr.otaq === n} onPress={() => setFiltr({ ...filtr, otaq: n })} />
            ))}
          </View>
          <Text style={s.label}>Qiymət (AZN)</Text>
          <View style={s.row}>
            <TextInput style={s.input} placeholder="Min" placeholderTextColor={colors.muted} keyboardType="number-pad"
              value={filtr.minQiymet} onChangeText={(v) => setFiltr({ ...filtr, minQiymet: v })} />
            <TextInput style={s.input} placeholder="Max" placeholderTextColor={colors.muted} keyboardType="number-pad"
              value={filtr.maxQiymet} onChangeText={(v) => setFiltr({ ...filtr, maxQiymet: v })} />
          </View>
          <Text style={s.label}>Rayon</Text>
          <ScrollView horizontal showsHorizontalScrollIndicator={false} contentContainerStyle={s.chips}>
            <Chip ad="Hamısı" aktiv={filtr.rayon == null} onPress={() => setFiltr({ ...filtr, rayon: null })} />
            {rayonlar.map((r) => (
              <Chip key={r} ad={r} aktiv={filtr.rayon === r} onPress={() => setFiltr({ ...filtr, rayon: r })} />
            ))}
          </ScrollView>
          <Pressable onPress={() => setFiltr(BOS_FILTR)}>
            <Text style={s.reset}>Filtrləri sıfırla</Text>
          </Pressable>
        </View>
      )}

      {xeta ? <Text style={s.err}>{xeta}</Text> : null}
      {yuklenir && elanlar.length === 0 ? (
        <ActivityIndicator style={{ marginTop: 40 }} color={colors.accent} />
      ) : (
        <FlatList
          data={elanlar}
          keyExtractor={(e) => `${e.menba}:${e.elan_id}`}
          renderItem={renderItem}
          contentContainerStyle={{ padding: 12, gap: 10 }}
          refreshControl={<RefreshControl refreshing={yenilenir} onRefresh={yenile} tintColor={colors.accent} />}
          onEndReachedThreshold={0.4}
          onEndReached={() => daha && !yuklenir && yukle(filtr, elanlar.length)}
          ListEmptyComponent={<Text style={s.empty}>Bu filtrə uyğun elan yoxdur.</Text>}
          ListFooterComponent={daha && elanlar.length > 0 ? <ActivityIndicator color={colors.accent} style={{ margin: 12 }} /> : undefined}
        />
      )}
    </View>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  bar: { flexDirection: "row", alignItems: "center", paddingLeft: 12, paddingVertical: 8, borderBottomWidth: 1, borderBottomColor: colors.line },
  chips: { flexDirection: "row", gap: 8, alignItems: "center" },
  chip: { borderWidth: 1, borderColor: colors.line, backgroundColor: colors.card, borderRadius: 18, paddingVertical: 7, paddingHorizontal: 14 },
  chipOn: { backgroundColor: colors.accent, borderColor: colors.accent },
  chipText: { color: colors.ink, fontWeight: "600" },
  chipTextOn: { color: "#fff" },
  filtrBtn: { paddingHorizontal: 14, paddingVertical: 8 },
  filtrBtnText: { color: colors.accent, fontWeight: "700" },
  panel: { padding: 12, gap: 8, backgroundColor: colors.card, borderBottomWidth: 1, borderBottomColor: colors.line },
  label: { color: colors.muted, fontWeight: "700", marginTop: 4 },
  input: { flex: 1, borderWidth: 1, borderColor: colors.line, borderRadius: 8, padding: 10, color: colors.ink, backgroundColor: colors.bg },
  reset: { color: colors.suspect, fontWeight: "600", marginTop: 6 },
  card: { backgroundColor: colors.card, borderRadius: 12, padding: 14, gap: 4, borderWidth: 1, borderColor: colors.line },
  row: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", gap: 8 },
  price: { fontSize: 20, fontWeight: "800", color: colors.ink },
  badge: { color: "#fff", fontWeight: "700", fontSize: 12, paddingVertical: 3, paddingHorizontal: 9, borderRadius: 10, overflow: "hidden" },
  line: { color: colors.ink, fontSize: 15 },
  muted: { color: colors.muted, fontSize: 13, flexShrink: 1 },
  time: { color: colors.muted, fontSize: 12 },
  err: { color: colors.suspect, padding: 12 },
  empty: { textAlign: "center", color: colors.muted, marginTop: 40 },
});
