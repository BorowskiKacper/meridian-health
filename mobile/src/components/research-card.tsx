import { StyleSheet, Text, View } from "react-native";

import { theme } from "../theme";
import type { Answer } from "../types";

export function ResearchCard({ answer }: { answer: Answer }) {
  return (
    <View style={styles.card}>
      <Text style={styles.basis}>Answer from the clinic API.</Text>
      <Text style={styles.answer}>{answer.text}</Text>
      {answer.citations.length > 0 ? (
        <View style={styles.list}>
          {answer.citations.map((citation, index) => (
            <View key={`${citation.source_id}:${citation.locator}`} style={styles.item}>
              <Text style={styles.index}>{index + 1}</Text>
              <Text style={styles.source}>{citation.title || citation.source_id || "Source"}</Text>
            </View>
          ))}
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: theme.ivory06,
    borderColor: theme.ivory14,
    borderRadius: 8,
    borderWidth: 1,
    marginTop: 16,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  basis: { color: theme.ivory45, fontSize: 12, fontStyle: "italic" },
  answer: { color: theme.ivory65, fontSize: 14, lineHeight: 22, marginTop: 8 },
  list: { gap: 6, marginTop: 12 },
  item: { flexDirection: "row", gap: 8 },
  index: { color: theme.jade300, fontSize: 12, fontVariant: ["tabular-nums"] },
  source: { color: theme.ivory65, flex: 1, fontSize: 12, lineHeight: 16 },
});
