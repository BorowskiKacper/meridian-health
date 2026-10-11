import { ActivityIndicator, Pressable, StyleSheet, Text, View } from 'react-native';

type Props = {
  recording: boolean;
  busy: boolean;
  onPress: () => void;
};

export function DictationButton({ recording, busy, onPress }: Props) {
  return (
    <View style={styles.wrap}>
      <View style={[styles.halo, recording && styles.haloRecording]}>
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={busy ? 'Sending request' : recording ? 'Stop and send dictation' : 'Start dictation'}
          accessibilityHint={recording ? 'Stops recording and sends your voice request to your laptop.' : 'Tap once to start recording. Tap again to stop and send.'}
          accessibilityState={{ disabled: busy, busy }}
          disabled={busy}
          onPress={onPress}
          style={({ pressed }) => [styles.button, recording && styles.recording, busy && styles.disabled, pressed && styles.pressed]}
        >
          {busy ? <ActivityIndicator color="#fffdf7" size="large" /> : recording ? (
            <View style={styles.stop} />
          ) : (
            <View style={styles.icon}>
              <View style={styles.head} />
              <View style={styles.cup} />
              <View style={styles.stem} />
              <View style={styles.base} />
            </View>
          )}
        </Pressable>
      </View>
      <Text accessibilityLiveRegion="polite" style={[styles.label, recording && styles.recordingLabel]}>
        {busy ? 'Sending…' : recording ? 'Listening · tap to stop & send' : 'Tap to dictate'}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  wrap: { alignItems: 'center', gap: 8, paddingVertical: 4 },
  halo: { width: 120, height: 120, borderRadius: 60, backgroundColor: '#e4eee7', alignItems: 'center', justifyContent: 'center' },
  haloRecording: { backgroundColor: '#f3e2da' },
  button: { width: 104, height: 104, borderRadius: 52, backgroundColor: '#30564b', alignItems: 'center', justifyContent: 'center' },
  recording: { backgroundColor: '#9a422f' },
  disabled: { opacity: 0.65 },
  pressed: { opacity: 0.85, transform: [{ scale: 0.96 }] },
  label: { color: '#30564b', fontSize: 14, fontWeight: '600', textAlign: 'center' },
  recordingLabel: { color: '#9a422f' },
  stop: { width: 28, height: 28, borderRadius: 5, backgroundColor: '#fffdf7' },
  icon: { width: 38, height: 48, alignItems: 'center' },
  head: { width: 20, height: 29, borderRadius: 10, borderWidth: 3, borderColor: '#fffdf7' },
  cup: { width: 34, height: 22, marginTop: -14, borderWidth: 3, borderTopWidth: 0, borderColor: '#fffdf7', borderBottomLeftRadius: 17, borderBottomRightRadius: 17 },
  stem: { width: 3, height: 8, backgroundColor: '#fffdf7' },
  base: { width: 19, height: 3, borderRadius: 2, backgroundColor: '#fffdf7' },
});
