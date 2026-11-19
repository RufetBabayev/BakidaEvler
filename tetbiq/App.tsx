import { useEffect, useState } from "react";
import { ActivityIndicator, Pressable, SafeAreaView, StyleSheet, Text, View } from "react-native";
import { StatusBar } from "expo-status-bar";
import type { Session } from "@supabase/supabase-js";
import ListScreen from "./src/ListScreen";
import LoginScreen from "./src/LoginScreen";
import { supabase } from "./src/supabase";
import { colors } from "./src/theme";

export default function App() {
  const [session, setSession] = useState<Session | null>(null);
  const [hazir, setHazir] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data }) => {
      setSession(data.session);
      setHazir(true);
    });
    const { data: sub } = supabase.auth.onAuthStateChange((_e, s) => setSession(s));
    return () => sub.subscription.unsubscribe();
  }, []);

  if (!hazir) {
    return <View style={s.center}><ActivityIndicator color={colors.accent} /></View>;
  }

  return (
    <SafeAreaView style={s.root}>
      <StatusBar style="dark" />
      {session ? (
        <>
          <View style={s.header}>
            <Text style={s.title}>BakıdaEvlər.az</Text>
            <Pressable onPress={() => supabase.auth.signOut()}>
              <Text style={s.out}>Çıxış</Text>
            </Pressable>
          </View>
          <ListScreen />
        </>
      ) : (
        <LoginScreen />
      )}
    </SafeAreaView>
  );
}

const s = StyleSheet.create({
  root: { flex: 1, backgroundColor: colors.bg },
  center: { flex: 1, alignItems: "center", justifyContent: "center", backgroundColor: colors.bg },
  header: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", paddingHorizontal: 16, paddingTop: 36, paddingBottom: 10 },
  title: { fontSize: 22, fontWeight: "800", color: colors.accent },
  out: { color: colors.muted, fontWeight: "600" },
});
