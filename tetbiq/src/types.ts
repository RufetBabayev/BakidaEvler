export type Elan = {
  menba: string;
  elan_id: string;
  link: string | null;
  qiymet: number | null;
  valyuta: string | null;
  kateqoriya: string | null;
  otaq_sayi: number | null;
  sahe_m2: number | null;
  rayon: string | null;
  metro: string | null;
  satici_tipi: string | null;
  satici_adi: string | null;
  telefon: string | null;
  telefon_elan_sayi: number | null;
  makler_netice: string | null;
  ilk_gorulme: string;
  data: { mərtəbə?: number | null; ümumi_mərtəbə?: number | null; başlıq?: string } | null;
};

export type Satici = "hamisi" | "ev sahibi" | "subheli" | "makler";

export type Filtr = {
  satici: Satici;
  otaq: number | null; // 5 = 5 və çox
  minQiymet: string;
  maxQiymet: string;
  rayon: string | null;
};

export const BOS_FILTR: Filtr = { satici: "hamisi", otaq: null, minQiymet: "", maxQiymet: "", rayon: null };
