class SpeechHook:
    def transcribe(self, audio):
        raise NotImplementedError

    def synthesize(self, text):
        raise NotImplementedError
