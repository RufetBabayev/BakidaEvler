import { Platform } from "react-native";
import Constants from "expo-constants";
import * as Notifications from "expo-notifications";
import { supabase } from "./supabase";

// Tətbiq açıq olanda da bildiriş görünsün
Notifications.setNotificationHandler({
  handleNotification: async () => ({
    shouldPlaySound: true,
    shouldSetBadge: false,
    shouldShowBanner: true,
    shouldShowList: true,
  }),
});

/**
 * Telefondan bildiriş icazəsi istəyir (Android 13+ icazə pəncərəsi çıxır), Expo push tokenini alır
 * və Supabase-də saxlayır ki, toplayıcı yeni ev sahibi elanı tapanda bu telefona bildiriş göndərsin.
 * Uğursuz olarsa tətbiq işləməyə davam edir (bildiriş olmadan).
 */
export async function registerForPush(): Promise<string | null> {
  try {
    if (Platform.OS === "android") {
      await Notifications.setNotificationChannelAsync("default", {
        name: "Yeni ev sahibi elanları",
        importance: Notifications.AndroidImportance.MAX,
        vibrationPattern: [0, 250, 250, 250],
      });
    }

    const existing = await Notifications.getPermissionsAsync();
    let status = existing.status;
    if (status !== "granted") {
      status = (await Notifications.requestPermissionsAsync()).status;
    }
    if (status !== "granted") return null;

    const projectId = Constants?.expoConfig?.extra?.eas?.projectId ?? Constants?.easConfig?.projectId;
    if (!projectId) return null;

    const { data: token } = await Notifications.getExpoPushTokenAsync({ projectId });
    const { error } = await supabase.from("push_tokenlar").upsert({ token }, { onConflict: "token" });
    if (error) return null;
    return token;
  } catch {
    return null;
  }
}
