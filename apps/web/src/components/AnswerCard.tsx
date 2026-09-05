import { forwardRef } from "react";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";

type AnswerCardProps = {
  userQuery?: string;
  answer?: string;
};

export const AnswerCard = forwardRef<HTMLDivElement, AnswerCardProps>(
  ({ userQuery, answer }, ref) => {
    return (
      <div className="space-y-4">
        {userQuery && (
          <div className="rounded-xl border bg-muted/40 p-4">
            <p className="text-sm text-foreground/80 italic">{userQuery}</p>
          </div>
        )}

        <div ref={ref} className="rounded-xl border bg-card p-5 md:p-6">
          <h2 className="mb-4 text-sm font-semibold text-primary">Jawaban</h2>
          <div className="markdown-body text-sm leading-relaxed text-foreground/90 space-y-3 [&_strong]:font-semibold [&_strong]:text-foreground [&_ul]:list-disc [&_ul]:pl-5 [&_ol]:list-decimal [&_ol]:pl-5 [&_li]:my-1 [&_a]:text-primary [&_a]:underline [&_code]:bg-muted [&_code]:px-1 [&_code]:py-0.5 [&_code]:rounded [&_code]:text-xs [&_h1]:text-lg [&_h1]:font-semibold [&_h2]:text-base [&_h2]:font-semibold [&_h3]:font-semibold [&_p]:leading-relaxed [&_blockquote]:border-l-4 [&_blockquote]:border-primary/40 [&_blockquote]:pl-3 [&_blockquote]:italic">
            {answer ? (
              <ReactMarkdown remarkPlugins={[remarkGfm]}>{answer}</ReactMarkdown>
            ) : (
              <p className="text-muted-foreground">Tidak ada jawaban dari server.</p>
            )}
          </div>
        </div>
      </div>
    );
  },
);

AnswerCard.displayName = "AnswerCard";
