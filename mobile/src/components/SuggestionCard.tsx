import { useState } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";

import { confidenceLabel, diffLines, flagLabel, kindLabel } from "../format";
import type { Suggestion } from "../types";
import { CitationList } from "./CitationList";

type Props = {
  suggestion: Suggestion;
  busy: boolean;
  onApprove: (id: string) => void;
  onReject: (id: string, reason: string) => void;
};

export function SuggestionCard({ suggestion, busy, onApprove, onReject }: Props) {
  const [rejecting, setRejecting] = useState(false);
  const [reason, setReason] = useState("");
  const pending = suggestion.status === "pending";
  const lines = diffLines(suggestion.before, suggestion.after);
  const confidence = confidenceLabel(suggestion.confidence);

  return (
    <View style={styles.card}>
      <Text style={styles.kind}>{kindLabel(suggestion.kind)}</Text>
      {suggestion.reason ? <Text style={styles.reason}>{suggestion.reason}</Text> : null}
      {lines.map((line) => (
        <Text key={line} style={styles.diff}>
          {line}
        </Text>
      ))}
      {confidence ? <Text style={styles.meta}>{confidence}</Text> : null}
      {suggestion.validation_flags.map((flag) => (
        <Text key={flag} style={styles.flag}>
          {flagLabel(flag)}
        </Text>
      ))}
      <CitationList citations={suggestion.citations} />
      {pending ? (
        <View style={styles.actions}>
          <Pressable
            accessibilityLabel={`Approve ${suggestion.reason || suggestion.kind}`}
            disabled={busy}
            onPress={() => onApprove(suggestion.id)}
            style={[styles.approve, busy && styles.disabled]}
          >
            <Text style={styles.approveText}>{busy ? "Approving..." : "Approve"}</Text>
          </Pressable>
          <Pressable
            accessibilityLabel={`Reject ${suggestion.reason || suggestion.kind}`}
            disabled={busy}
            onPress={() => setRejecting((open) => !open)}
            style={styles.reject}
          >
            <Text style={styles.rejectText}>Reject</Text>
          </Pressable>
        </View>
      ) : (
        <Text style={styles.meta}>{suggestion.status}</Text>
      )}
      {pending && rejecting ? (
        <View style={styles.rejectBox}>
          <TextInput
            accessibilityLabel="Rejection reason"
            onChangeText={setReason}
            placeholder="Why reject this?"
            placeholderTextColor="#8a8178"
            style={styles.reasonInput}
            value={reason}
          />
          <Pressable
            accessibilityLabel="Confirm reject"
            disabled={busy || !reason.trim()}
            onPress={() => onReject(suggestion.id, reason.trim())}
            style={[styles.confirm, (!reason.trim() || busy) && styles.disabled]}
          >
            <Text style={styles.rejectText}>Confirm reject</Text>
          </Pressable>
        </View>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#fffdf7",
    borderColor: "#cbdacf",
    borderRadius: 12,
    borderWidth: 1,
    gap: 6,
    padding: 12,
  },
  kind: {
    color: "#62776b",
    fontSize: 12,
    fontWeight: "600",
    letterSpacing: 0.4,
    textTransform: "uppercase",
  },
  reason: { color: "#273d31", fontSize: 16, lineHeight: 22 },
  diff: { color: "#556b60", fontSize: 14, lineHeight: 20 },
  meta: { color: "#62776b", fontSize: 13 },
  flag: { color: "#8c3a32", fontSize: 13, fontWeight: "600" },
  actions: { flexDirection: "row", gap: 8, marginTop: 4 },
  approve: {
    backgroundColor: "#30564b",
    borderRadius: 999,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  approveText: { color: "#f4fbf8", fontSize: 14, fontWeight: "600" },
  reject: {
    borderColor: "#8c3a32",
    borderRadius: 999,
    borderWidth: 1,
    paddingHorizontal: 14,
    paddingVertical: 8,
  },
  rejectText: { color: "#8c3a32", fontSize: 14, fontWeight: "600" },
  rejectBox: { gap: 8 },
  reasonInput: {
    borderColor: "#cbdacf",
    borderRadius: 10,
    borderWidth: 1,
    color: "#273d31",
    fontSize: 15,
    paddingHorizontal: 10,
    paddingVertical: 8,
  },
  confirm: { alignSelf: "flex-start" },
  disabled: { opacity: 0.45 },
});
