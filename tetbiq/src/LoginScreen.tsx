import { useState } from "react";
import { ActivityIndicator, KeyboardAvoidingView, Platform, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { supabase } from "./supabase";
import { colors } from "./theme";

export default function LoginScreen() {
  const [email, setEmail] = useState("");
  const [parol, setParol] = useState("");
  const [yuklenir, setYuklenir] = useState(false);
  const [xeta, setXeta] = useState<string | null>(null);

  async function daxilOl() {
    setYuklenir(true);
    setXeta(null);
    const { error } = await supabase.auth.signInWithPassword({ email: email.trim(), password: parol });
    if (error) setXeta("E-poçt və ya parol səhvdir.");
    setYuklenir(false);
  }

  return (
    <KeyboardAvoidingView style={s.root} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <Text style={s.title}>BakıdaEvlər.az</Text>
      <Text style={s.sub}>Yeni satış elanları: ev sahibi və makler ayrıca</Text>
      <TextInput
        style={s.input}
        placeholder="E-poçt"
        placeholderTextColor={colors.muted}
        autoCapitalize="none"
        keyboardType="email-address"
        autoComplete="email"
        value={email}
        onChangeText={setEmail}
      />
      <TextInput
        style={s.input}
        placeholder="Parol"
        placeholderTextColor={colors.muted}
        secureTextEntry
        autoComplete="password"
        value={parol}
        onChangeText={setParol}
        onSubmitEditing={daxilOl}
      />
      {xeta ? <Text style={s.err}>{xeta}</Text> : null}
      <Pressable style={[s.btn, (!email || !parol) && { opacity: 0.5 }]} onPress={daxilOl} disabled={!email || !parol || yuklenir}>
        {yuklenir ? <ActivityIndicator color="#fff" /> : <Text style={s.btnText}>Daxil ol</Text>}
      </Pressable>
    </KeyboardAvoidingView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg, justifyContent: "center", padding: 24, gap: 12 },
  title: { fontSize: 30, fontWeight: "800", color: colors.accent },
  sub: { color: colors.muted, marginBottom: 12 },
  input: { backgroundColor: colors.card, borderWidth: 1, borderColor: colors.line, borderRadius: 10, padding: 14, fontSize: 16, color: colors.ink },
  err: { color: colors.suspect },
  btn: { backgroundColor: colors.accent, borderRadius: 10, padding: 15, alignItems: "center", marginTop: 4 },
  btnText: { color: "#fff", fontWeight: "700", fontSize: 16 },
});
