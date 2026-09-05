import { Button } from "@/components/ui/button";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";
import { Send } from "lucide-react";
import { useEffect, useRef, useState, type KeyboardEvent } from "react";

const EXAMPLES = [
  "Apa fungsi kartu bimbingan skripsi di universitas negeri malang?",
  "Bagaimana cara mengajukan cuti kuliah di um?",
  "Ada berapa prodi di fakultas teknik um?",
  "Apa saja syarat dan tahapan registrasi mahasiswa baru jalur UTBK-SNBT 2024 di UM?",
  "Bagaimana prosedur pembimbingan skripsi di Universitas Negeri Malang dari awal sampai akhir?",
  "Ada berapa fakultas di universitas negeri malang?",
];

type CharacterToken = {
  id: number;
  value: string;
  animate: boolean;
};

export function ChatInput({
  value,
  onChange,
  onSubmit,
  loading,
}: {
  value: string;
  onChange: (v: string) => void;
  onSubmit: () => void;
  loading: boolean;
}) {
  const nextTokenId = useRef(0);
  const mirrorRef = useRef<HTMLDivElement | null>(null);
  const animationTimerRef = useRef<number | null>(null);
  const [tokens, setTokens] = useState<CharacterToken[]>(() =>
    splitCharacters(value).map((char) => ({
      id: nextTokenId.current++,
      value: char,
      animate: false,
    })),
  );
  const [pickedExample, setPickedExample] = useState<string | null>(null);

  useEffect(() => {
    return () => {
      if (animationTimerRef.current !== null) {
        window.clearTimeout(animationTimerRef.current);
      }
    };
  }, []);

  const syncTokens = (nextValue: string) => {
    setTokens((currentTokens) => {
      const currentChars = currentTokens.map((token) => token.value);
      const nextChars = splitCharacters(nextValue);
      let prefixLength = 0;

      while (
        prefixLength < currentChars.length &&
        prefixLength < nextChars.length &&
        currentChars[prefixLength] === nextChars[prefixLength]
      ) {
        prefixLength++;
      }

      let suffixLength = 0;
      while (
        suffixLength < currentChars.length - prefixLength &&
        suffixLength < nextChars.length - prefixLength &&
        currentChars[currentChars.length - 1 - suffixLength] ===
          nextChars[nextChars.length - 1 - suffixLength]
      ) {
        suffixLength++;
      }

      const insertedChars = nextChars.slice(prefixLength, nextChars.length - suffixLength);
      const insertedTokens = insertedChars.map((char) => ({
        id: nextTokenId.current++,
        value: char,
        animate: true,
      }));
      const suffixStart = currentTokens.length - suffixLength;

      return [
        ...currentTokens.slice(0, prefixLength),
        ...insertedTokens,
        ...currentTokens.slice(suffixStart),
      ];
    });
  };

  const settleCharacterAnimations = () => {
    if (animationTimerRef.current !== null) {
      window.clearTimeout(animationTimerRef.current);
    }
    animationTimerRef.current = window.setTimeout(() => {
      setTokens((currentTokens) =>
        currentTokens.map((token) => (token.animate ? { ...token, animate: false } : token)),
      );
    }, 220);
  };

  const handleChange = (nextValue: string) => {
    syncTokens(nextValue);
    settleCharacterAnimations();
    onChange(nextValue);
  };

  const pickExample = (q: string) => {
    setPickedExample(q);
    syncTokens(q);
    settleCharacterAnimations();
    onChange(q);
    window.setTimeout(() => setPickedExample(null), 620);
  };

  const handleKey = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && (e.ctrlKey || e.metaKey)) {
      e.preventDefault();
      if (!loading && value.trim()) onSubmit();
    }
  };

  return (
    <div className="space-y-4">
      <div className="rounded-xl border bg-card overflow-hidden focus-within:ring-2 focus-within:ring-ring/40 transition">
        <div className="relative">
          <div
            ref={mirrorRef}
            aria-hidden="true"
            className="chat-input-text-metrics pointer-events-none absolute inset-0 min-h-24 overflow-hidden whitespace-pre-wrap break-words px-5 py-4 text-foreground"
          >
            {tokens.map((token) => (
              <span
                key={token.id}
                className={cn(
                  token.animate && "inline-block origin-bottom-left align-baseline",
                  token.animate && "motion-char-reveal",
                )}
              >
                {token.value}
              </span>
            ))}
          </div>
          <Textarea
            value={value}
            onChange={(e) => handleChange(e.target.value)}
            onKeyDown={handleKey}
            onScroll={(event) => {
              if (!mirrorRef.current) return;
              mirrorRef.current.scrollTop = event.currentTarget.scrollTop;
              mirrorRef.current.scrollLeft = event.currentTarget.scrollLeft;
            }}
            placeholder="Tulis pertanyaan Anda di sini..."
            className="chat-input-text-metrics relative min-h-24 border-0 resize-none focus-visible:ring-0 px-5 py-4 bg-transparent text-transparent caret-primary selection:bg-primary/20"
            disabled={loading}
          />
        </div>
        <div className="flex items-center justify-end gap-3 px-4 py-3 border-t bg-muted/40">
          <Button onClick={onSubmit} disabled={loading || !value.trim()} className="min-h-11 gap-2">
            <Send className="h-4 w-4" />
            Tanyakan
          </Button>
        </div>
      </div>

      <div className="space-y-2">
        <span className="block text-xs text-muted-foreground">Contoh:</span>
        <div className="grid gap-2 sm:grid-cols-[repeat(auto-fit,minmax(260px,1fr))]">
          {EXAMPLES.map((q) => (
            <button
              key={q}
              type="button"
              onClick={() => pickExample(q)}
              disabled={loading}
              title={q}
              className={cn(
                "min-h-11 max-w-full truncate rounded-lg border bg-card px-3 py-2 text-left text-xs transition hover:bg-accent hover:text-accent-foreground active:scale-[0.97] disabled:opacity-50",
                pickedExample === q && "motion-example-picked",
              )}
            >
              {q}
            </button>
          ))}
        </div>
      </div>
    </div>
  );
}

function splitCharacters(value: string) {
  return Array.from(value);
}
