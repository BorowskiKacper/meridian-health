import { Pressable, StyleSheet, Text, View } from "react-native";

import { actionDetail, confidenceText, formatPatch } from "../chat";
import { theme } from "../theme";
import type { Suggestion } from "../types";

type Props = {
  suggestion: Suggestion;
  busy: boolean;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
};

export function ActionCard({ suggestion, busy, onApprove, onReject }: Props) {
  const pending = suggestion.status === "pending";
  const before = formatPatch(suggestion.before);
  const after = formatPatch(suggestion.after);
  const confidence = confidenceText(suggestion.confidence);
  const citations = suggestion.citations
    .map((citation) => citation.title || citation.source_id)
    .filter(Boolean);
  const meta = [suggestion.source, confidence, ...citations].filter(Boolean).join(" · ");

  return (
    <View style={[styles.card, suggestion.status === "rejected" && styles.rejected]}>
      <View style={styles.eyebrow}>
        <Text style={[styles.kind, pending ? styles.kindPending : styles.kindSettled]}>Chart change</Text>
        {pending ? null : (
          <Text style={styles.status}>
            {suggestion.status === "approved" ? "✓  Approved" : "✕  Rejected"}
          </Text>
        )}
      </View>
      <Text style={[styles.title, suggestion.status === "rejected" && styles.struck]}>
        {suggestion.reason || suggestion.kind}
      </Text>
      {before || after ? (
        <View style={styles.patch}>
          {before ? (
            <View style={styles.row}>
              <Text style={styles.dt}>Before</Text>
              <Text style={styles.ddSoft}>{before}</Text>
            </View>
          ) : null}
          {after ? (
            <View style={styles.row}>
              <Text style={styles.dt}>After</Text>
              <Text style={styles.dd}>{after}</Text>
            </View>
          ) : null}
        </View>
      ) : (
        <Text style={styles.detail}>{actionDetail(suggestion)}</Text>
      )}
      {meta ? <Text style={styles.meta}>{meta}</Text> : null}
      {pending ? (
        <View style={styles.actions}>
          <Pressable
            accessibilityLabel={`Approve ${suggestion.reason}`}
            disabled={busy}
            onPress={() => onApprove(suggestion.id)}
          >
            <Text style={[styles.action, busy && styles.disabled]}>Approve</Text>
          </Pressable>
          <Pressable
            accessibilityLabel={`Reject ${suggestion.reason}`}
            disabled={busy}
            onPress={() => onReject(suggestion.id)}
          >
            <Text style={[styles.action, busy && styles.disabled]}>Reject</Text>
          </Pressable>
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
    borderStyle: "dashed",
    borderWidth: 1,
    marginTop: 10,
    paddingHorizontal: 16,
    paddingVertical: 14,
  },
  rejected: { opacity: 0.55 },
  eyebrow: { alignItems: "center", flexDirection: "row", gap: 12 },
  kind: { fontSize: 11, fontWeight: "600", letterSpacing: 1.4, textTransform: "uppercase" },
  kindPending: { color: theme.jade300 },
  kindSettled: { color: theme.ivory45 },
  status: { color: theme.ivory45, fontSize: 12, marginLeft: "auto" },
  title: { color: theme.ivory, fontSize: 15, fontWeight: "600", marginTop: 12 },
  struck: { textDecorationLine: "line-through" },
  patch: { gap: 12, marginTop: 12 },
  row: { flexDirection: "row", gap: 16 },
  dt: { color: theme.ivory45, fontSize: 13, width: 52 },
  dd: { color: theme.ivory, flex: 1, fontSize: 13, lineHeight: 18 },
  ddSoft: { color: theme.ivory65, flex: 1, fontSize: 13, lineHeight: 18 },
  detail: { color: theme.ivory65, fontSize: 13, marginTop: 4 },
  meta: { color: theme.ivory45, fontSize: 12, lineHeight: 18, marginTop: 16 },
  actions: { flexDirection: "row", gap: 18, marginTop: 20 },
  action: { color: theme.jade300, fontSize: 14, fontWeight: "600" },
  disabled: { opacity: 0.4 },
});
