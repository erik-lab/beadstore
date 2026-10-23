import { useCallback, useEffect, useRef, useState } from "react";

/**
 * Speech-to-text for inventory entry, using the browser's own recognition.
 *
 * Transcription happens in the browser rather than on the server: the audio
 * never leaves the machine, there's no audio upload or transcription service
 * to pay for, and the result is plain text that goes through the exact same
 * parser as a pasted note.
 *
 * The trade-off is support — the Web Speech API is in Chrome and Edge, and
 * Safari behind a prefix, but not Firefox. Callers check `supported` and
 * offer typing instead, which costs nothing because the text box is already
 * there.
 */

// Minimal shape of the parts of the Web Speech API we use. The DOM lib
// doesn't declare these (it's not a finished standard), and the vendor-prefixed
// constructor means we'd be casting anyway.
interface SpeechRecognitionAlternative {
  transcript: string;
}
interface SpeechRecognitionResult {
  isFinal: boolean;
  0: SpeechRecognitionAlternative;
}
interface SpeechRecognitionEventLike {
  resultIndex: number;
  results: { length: number; [index: number]: SpeechRecognitionResult };
}
interface SpeechRecognitionErrorEventLike {
  error: string;
}
interface SpeechRecognitionLike {
  continuous: boolean;
  interimResults: boolean;
  lang: string;
  start(): void;
  stop(): void;
  abort(): void;
  onresult: ((event: SpeechRecognitionEventLike) => void) | null;
  onerror: ((event: SpeechRecognitionErrorEventLike) => void) | null;
  onend: (() => void) | null;
}
type SpeechRecognitionConstructor = new () => SpeechRecognitionLike;

function getConstructor(): SpeechRecognitionConstructor | null {
  const w = window as unknown as {
    SpeechRecognition?: SpeechRecognitionConstructor;
    webkitSpeechRecognition?: SpeechRecognitionConstructor;
  };
  return w.SpeechRecognition ?? w.webkitSpeechRecognition ?? null;
}

const ERROR_MESSAGES: Record<string, string> = {
  "not-allowed": "Microphone access was blocked. Allow it in your browser's address bar, then try again.",
  "service-not-allowed":
    "Microphone access was blocked. Allow it in your browser's address bar, then try again.",
  "no-speech": "Didn't catch anything — try again and speak a little closer to the mic.",
  "audio-capture": "No microphone was found. Check that one is plugged in and selected.",
  network: "Speech recognition needs a network connection and couldn't reach it.",
};

export interface Dictation {
  /** False in browsers without the Web Speech API (notably Firefox). */
  supported: boolean;
  listening: boolean;
  /** Words recognized so far but not yet finalized, for live feedback. */
  interim: string;
  error: string | null;
  start: () => void;
  stop: () => void;
}

/**
 * @param onFinalText Called with each finalized chunk of speech. Chunks
 * arrive as the speaker pauses, so the caller appends rather than replaces.
 */
export function useDictation(onFinalText: (text: string) => void): Dictation {
  const [listening, setListening] = useState(false);
  const [interim, setInterim] = useState("");
  const [error, setError] = useState<string | null>(null);
  const recognitionRef = useRef<SpeechRecognitionLike | null>(null);
  // Held in a ref so restarting recognition doesn't need a fresh callback,
  // and so the handler always calls the latest version.
  const onFinalTextRef = useRef(onFinalText);
  onFinalTextRef.current = onFinalText;

  const supported = typeof window !== "undefined" && getConstructor() !== null;

  const stop = useCallback(() => {
    recognitionRef.current?.stop();
    setListening(false);
    setInterim("");
  }, []);

  const start = useCallback(() => {
    const Constructor = getConstructor();
    if (!Constructor) {
      setError("This browser can't do speech recognition. Try Chrome or Edge, or type the entry instead.");
      return;
    }
    setError(null);
    setInterim("");

    const recognition = new Constructor();
    // continuous + interim results let Patti dictate several items in one go
    // and watch the words land, instead of one phrase per button press.
    recognition.continuous = true;
    recognition.interimResults = true;
    recognition.lang = navigator.language || "en-US";

    recognition.onresult = (event) => {
      let pending = "";
      for (let i = event.resultIndex; i < event.results.length; i += 1) {
        const result = event.results[i];
        if (result.isFinal) {
          onFinalTextRef.current(result[0].transcript);
        } else {
          pending += result[0].transcript;
        }
      }
      setInterim(pending);
    };

    recognition.onerror = (event) => {
      // "aborted" is what we get from our own stop() call — not worth showing.
      if (event.error !== "aborted") {
        setError(ERROR_MESSAGES[event.error] ?? `Speech recognition stopped (${event.error}).`);
      }
      setListening(false);
      setInterim("");
    };

    recognition.onend = () => {
      setListening(false);
      setInterim("");
    };

    recognitionRef.current = recognition;
    try {
      recognition.start();
      setListening(true);
    } catch {
      // Thrown if start() is called while already running; the existing
      // session is still live, so reflect that rather than reporting failure.
      setListening(true);
    }
  }, []);

  // Release the microphone if the page is left mid-dictation.
  useEffect(() => () => recognitionRef.current?.abort(), []);

  return { supported, listening, interim, error, start, stop };
}
