import { createAudioPlayer } from "expo-audio";
import { Platform } from "react-native";

export function playReadBack(audioBase64: string): void {
  const uri = `data:audio/mpeg;base64,${audioBase64}`;
  if (Platform.OS === "web") {
    const AudioCtor = (
      globalThis as { Audio?: new (src: string) => { play: () => Promise<void> } }
    ).Audio;
    if (AudioCtor) {
      void new AudioCtor(uri).play();
      return;
    }
  }
  createAudioPlayer(uri).play();
}
