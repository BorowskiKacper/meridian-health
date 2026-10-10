import { useEffect, useRef } from "react";
import { Animated, Pressable, ScrollView, StyleSheet, Text, View } from "react-native";

import { STARTERS, chatRouteLabel, type AgentTurn, type Turn } from "../chat";
import { serif, theme } from "../theme";
import { ResearchCard } from "./research-card";

type Props = {
  messages: Turn[];
  onStarter: (text: string) => void;
  onPlay: (audioBase64: string) => void;
};

export function Conversation({ messages, onStarter, onPlay }: Props) {
  const scroller = useRef<ScrollView>(null);
  const count = messages.length;
  const last = messages.at(-1);
  const lastText = last && "text" in last ? last.text : "";

  useEffect(() => {
    scroller.current?.scrollToEnd({ animated: true });
  }, [count, lastText]);

  return (
    <ScrollView
      contentContainerStyle={messages.length === 0 ? styles.emptyContent : styles.thread}
      ref={scroller}
      style={styles.scroll}
    >
      {messages.length === 0 ? (
        <View>
          <Text style={styles.heading}>How can I help?</Text>
          <Text style={styles.lead}>
            Ask a question here. Chart changes and the rest of the visit stay on the web app.
          </Text>
          <View style={styles.starters}>
            {STARTERS.map((starter) => (
              <Pressable key={starter} onPress={() => onStarter(starter)} style={styles.starter}>
                <Text style={styles.starterText}>{starter}</Text>
                <Text style={styles.arrow}>↗</Text>
              </Pressable>
            ))}
          </View>
        </View>
      ) : (
        messages.map((message) => (
          <View key={message.id}>
            {message.role === "doctor" ? (
              <DoctorMessage message={message} />
            ) : (
              <AgentMessage message={message} onPlay={onPlay} />
            )}
          </View>
        ))
      )}
    </ScrollView>
  );
}

function DoctorMessage({ message }: { message: Turn & { role: "doctor" } }) {
  return (
    <View style={styles.bubble}>
      <Text style={styles.bubbleText}>{message.text}</Text>
    </View>
  );
}

function AgentMessage({ message, onPlay }: { message: AgentTurn; onPlay: (audioBase64: string) => void }) {
  if (message.pending) return <Working />;
  return (
    <View>
      {message.route ? (
        <View style={styles.routeRow}>
          <Text style={styles.route}>{chatRouteLabel(message.route)}</Text>
          <Text style={styles.routed}>routed automatically</Text>
          {message.audioBase64 ? (
            <Pressable accessibilityLabel="Play read-back" onPress={() => onPlay(message.audioBase64 as string)}>
              <Text style={styles.play}>Play</Text>
            </Pressable>
          ) : null}
        </View>
      ) : null}
      {message.text ? <Text style={styles.body}>{message.text}</Text> : null}
      {message.answer ? <ResearchCard answer={message.answer} /> : null}
    </View>
  );
}

function Working() {
  const anim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    const loop = Animated.loop(
      Animated.sequence([
        Animated.timing(anim, { toValue: 1, duration: 700, useNativeDriver: true }),
        Animated.timing(anim, { toValue: 0, duration: 700, useNativeDriver: true }),
      ]),
    );
    loop.start();
    return () => loop.stop();
  }, [anim]);

  return (
    <View accessibilityLabel="Working" style={styles.dots}>
      {[0, 1, 2].map((index) => (
        <Animated.View
          key={index}
          style={[
            styles.dot,
            {
              opacity: anim.interpolate({
                inputRange: [0, 1],
                outputRange: index === 1 ? [0.35, 1] : [1, 0.35],
              }),
            },
          ]}
        />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  scroll: { flex: 1 },
  emptyContent: { flexGrow: 1, paddingBottom: 12, paddingTop: 28 },
  thread: { gap: 28, paddingBottom: 16, paddingTop: 24 },
  heading: { color: theme.ivory, fontFamily: serif, fontSize: 25, fontWeight: "400", lineHeight: 32 },
  lead: { color: theme.ivory65, fontSize: 14, lineHeight: 21, marginTop: 12 },
  starters: { borderColor: theme.ivory14, borderTopWidth: 1, marginTop: 24 },
  starter: {
    alignItems: "center",
    borderBottomWidth: 1,
    borderColor: theme.ivory14,
    flexDirection: "row",
    gap: 16,
    justifyContent: "space-between",
    paddingVertical: 12,
  },
  starterText: { color: theme.ivory65, flex: 1, fontSize: 14 },
  arrow: { color: theme.ivory65, fontSize: 14 },
  bubble: {
    alignSelf: "flex-end",
    backgroundColor: theme.ivory10,
    borderRadius: 8,
    maxWidth: "85%",
    paddingHorizontal: 16,
    paddingVertical: 10,
  },
  bubbleText: { color: theme.ivory, fontSize: 14, lineHeight: 21 },
  routeRow: { alignItems: "center", flexDirection: "row", gap: 8 },
  route: { color: theme.jade300, fontSize: 12, fontWeight: "600", letterSpacing: 1.4, textTransform: "uppercase" },
  routed: { color: theme.ivory45, fontSize: 12 },
  play: { color: theme.jade300, fontSize: 12, fontWeight: "600" },
  body: { color: theme.ivory, fontSize: 14, lineHeight: 22, marginTop: 6 },
  dots: { flexDirection: "row", gap: 6, paddingVertical: 4 },
  dot: { backgroundColor: "rgba(164,199,183,0.75)", borderRadius: 3, height: 6, width: 6 },
});
