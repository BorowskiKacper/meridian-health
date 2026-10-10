import { Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { isOpenableLocator } from "../format";
import type { Citation } from "../types";

export function CitationList({ citations }: { citations: Citation[] }) {
  if (citations.length === 0) return null;
  return (
    <View style={styles.list}>
      {citations.map((citation) => {
        const openable = isOpenableLocator(citation.locator);
        return (
          <View key={`${citation.source_id}:${citation.locator}`} style={styles.item}>
            <Text style={styles.tier}>{citation.tier}</Text>
            {openable ? (
              <Pressable
                accessibilityLabel={`Open ${citation.title}`}
                onPress={() => {
                  void Linking.openURL(citation.locator);
                }}
              >
                <Text style={styles.link}>{citation.title}</Text>
              </Pressable>
            ) : (
              <Text style={styles.title}>{citation.title}</Text>
            )}
            <Text style={styles.passage}>{citation.passage}</Text>
            {openable ? null : <Text style={styles.locator}>{citation.locator}</Text>}
          </View>
        );
      })}
    </View>
  );
}

const styles = StyleSheet.create({
  list: { gap: 8 },
  item: { gap: 2 },
  tier: {
    color: "#1f6f5b",
    fontSize: 11,
    fontWeight: "700",
    letterSpacing: 0.4,
    textTransform: "uppercase",
  },
  title: { color: "#1f1a17", fontSize: 14, fontWeight: "600" },
  link: { color: "#1f6f5b", fontSize: 14, fontWeight: "600", textDecorationLine: "underline" },
  passage: { color: "#3f3833", fontSize: 13, lineHeight: 18 },
  locator: { color: "#6d645c", fontSize: 12 },
});
