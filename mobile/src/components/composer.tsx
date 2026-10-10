import { useEffect, useRef } from "react";
import { Animated, Easing, Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { MODES, type ChatMode } from "../chat";
import { theme } from "../theme";

type Props = {
  patientName: string;
  mode: ChatMode;
  text: string;
  listening: boolean;
  busy: boolean;
  onMode: (mode: ChatMode) => void;
  onText: (text: string) => void;
  onSend: () => void;
  onDictate: () => void;
  onCancelDictation: () => void;
};

export function Composer({
  patientName,
  mode,
  text,
  listening,
  busy,
  onMode,
  onText,
  onSend,
  onDictate,
  onCancelDictation,
}: Props) {
  const canSend = Boolean(text.trim()) && !busy && !listening;
  const ring = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    if (!listening) {
      ring.setValue(0);
      return;
    }
    const loop = Animated.loop(
      Animated.timing(ring, {
        toValue: 1,
        duration: 1400,
        easing: Easing.out(Easing.ease),
        useNativeDriver: true,
      }),
    );
    loop.start();
    return () => loop.stop();
  }, [listening, ring]);

  return (
    <View style={styles.wrap}>
      <View style={styles.card}>
        <TextInput
          accessibilityLabel={`Message about ${patientName}`}
          editable={!busy && !listening}
          multiline
          onChangeText={onText}
          onSubmitEditing={onSend}
          placeholder={listening ? "Listening…" : `Message about ${patientName}`}
          placeholderTextColor={theme.ivory65}
          style={styles.field}
          value={listening ? "" : text}
        />
        <View style={styles.toolbar}>
          <View accessibilityRole="radiogroup" style={styles.modes}>
            {MODES.map((item) => {
              const selected = mode === item.id;
              return (
                <Pressable
                  accessibilityHint={item.hint}
                  accessibilityLabel={item.label}
                  accessibilityRole="radio"
                  accessibilityState={{ selected }}
                  key={item.id}
                  onPress={() => onMode(item.id)}
                  style={[styles.mode, selected && styles.modeOn]}
                >
                  <Text style={[styles.modeText, selected && styles.modeTextOn]}>{item.label}</Text>
                </Pressable>
              );
            })}
          </View>
          <Pressable
            accessibilityLabel="Send"
            disabled={!canSend}
            onPress={onSend}
            style={[styles.send, canSend ? styles.sendOn : styles.sendOff]}
          >
            <ArrowUp color={canSend ? theme.jade900 : theme.ivory35} />
          </Pressable>
        </View>
      </View>

      <View style={styles.dictate}>
        <View style={styles.micWrap}>
          {listening ? (
            <Animated.View
              style={[
                styles.ring,
                {
                  opacity: ring.interpolate({ inputRange: [0, 1], outputRange: [0.55, 0] }),
                  transform: [{ scale: ring.interpolate({ inputRange: [0, 1], outputRange: [1, 1.55] }) }],
                },
              ]}
            />
          ) : null}
          <Pressable
            accessibilityLabel={listening ? "Send dictation" : "Dictate"}
            accessibilityState={{ selected: listening }}
            disabled={busy}
            onPress={onDictate}
            style={[styles.mic, listening && styles.micOn, busy && styles.disabled]}
          >
            <MicMark color={theme.jade900} />
          </Pressable>
        </View>
        <Text style={styles.dictateLabel}>{listening ? "Listening" : "Dictate"}</Text>
        {listening ? (
          <Pressable accessibilityLabel="Cancel dictation" onPress={onCancelDictation}>
            <Text style={styles.cancel}>Cancel</Text>
          </Pressable>
        ) : (
          <Text style={styles.hint}>Tap to dictate. Tap again to send the recording.</Text>
        )}
      </View>
    </View>
  );
}

function ArrowUp({ color }: { color: string }) {
  return (
    <View style={styles.arrow}>
      <View
        style={{
          borderBottomColor: color,
          borderBottomWidth: 6,
          borderLeftColor: "transparent",
          borderLeftWidth: 5,
          borderRightColor: "transparent",
          borderRightWidth: 5,
          height: 0,
          width: 0,
        }}
      />
      <View style={{ backgroundColor: color, height: 8, width: 2 }} />
    </View>
  );
}

function MicMark({ color }: { color: string }) {
  return (
    <View style={styles.micIcon}>
      <View style={[styles.micHead, { borderColor: color }]} />
      <View style={[styles.micCup, { borderColor: color }]} />
      <View style={[styles.micStem, { backgroundColor: color }]} />
      <View style={[styles.micBase, { backgroundColor: color }]} />
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { gap: 18, paddingBottom: 22, paddingTop: 4 },
  card: {
    backgroundColor: theme.ivory08,
    borderColor: theme.ivory20,
    borderRadius: 8,
    borderWidth: 1,
  },
  field: {
    color: theme.ivory,
    fontSize: 16,
    lineHeight: 22,
    maxHeight: 140,
    minHeight: 52,
    paddingBottom: 4,
    paddingHorizontal: 16,
    paddingTop: 14,
  },
  toolbar: { alignItems: "center", flexDirection: "row", gap: 8, paddingBottom: 8, paddingHorizontal: 8 },
  modes: { flex: 1, flexDirection: "row", flexWrap: "wrap", gap: 2 },
  mode: { borderRadius: 6, paddingHorizontal: 8, paddingVertical: 6 },
  modeOn: { backgroundColor: theme.ivory14 },
  modeText: { color: theme.ivory70, fontSize: 12 },
  modeTextOn: { color: theme.ivory, fontWeight: "600" },
  send: { alignItems: "center", borderRadius: 16, height: 32, justifyContent: "center", width: 32 },
  sendOn: { backgroundColor: theme.jade300 },
  sendOff: { backgroundColor: theme.ivory10 },
  arrow: { alignItems: "center" },
  dictate: { alignItems: "center", gap: 8 },
  micWrap: { alignItems: "center", height: 92, justifyContent: "center", width: 92 },
  ring: {
    backgroundColor: "rgba(164,199,183,0.45)",
    borderRadius: 46,
    height: 84,
    position: "absolute",
    width: 84,
  },
  mic: {
    alignItems: "center",
    backgroundColor: theme.jade300,
    borderRadius: 38,
    height: 76,
    justifyContent: "center",
    width: 76,
  },
  micOn: { backgroundColor: theme.jade100 },
  disabled: { opacity: 0.4 },
  micIcon: { alignItems: "center", height: 28, width: 22 },
  micHead: {
    borderRadius: 7,
    borderWidth: 2,
    height: 14,
    width: 12,
  },
  micCup: {
    borderBottomLeftRadius: 10,
    borderBottomRightRadius: 10,
    borderTopWidth: 0,
    borderWidth: 2,
    height: 8,
    marginTop: -4,
    width: 18,
  },
  micStem: { height: 5, width: 2 },
  micBase: { height: 2, width: 12 },
  dictateLabel: { color: theme.ivory, fontSize: 15, fontWeight: "600" },
  hint: { color: theme.ivory45, fontSize: 12, textAlign: "center" },
  cancel: { color: theme.ivory65, fontSize: 14, fontWeight: "600" },
});
