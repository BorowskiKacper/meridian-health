"""Check cited sentences and drop any citation a surviving sentence does not use."""


def verify_claims(text, citations):
    import app.agents.doctor.model as model

    verdict = model.complete("verify", {"text": text, "citations": citations})
    kept = set()
    sentences = []
    for item in verdict.get("supported") or []:
        sentences.append(item["sentence"])
        for index in item.get("citation_indexes") or []:
            # bool is a subclass of int; True must not be treated as citation 1.
            if type(index) is int and 0 <= index < len(citations):
                kept.add(index)
    return {
        "text": " ".join(sentences),
        "citations": [
            citations[index] for index in range(len(citations)) if index in kept
        ],
        "removed": verdict.get("removed"),
    }
