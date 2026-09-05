import { Progress } from "@/components/ui/progress";
import { Button } from "@/components/ui/button";
import { Loader2, X } from "lucide-react";

export function ProgressCard({
  progress,
  message,
  onCancel,
}: {
  progress: number;
  message: string;
  onCancel?: () => void;
}) {
  return (
    <div className="rounded-xl border bg-card p-5">
      <div className="flex flex-wrap items-center gap-3 mb-3">
        <Loader2 className="h-4 w-4 animate-spin text-primary" />
        <span className="min-w-0 flex-1 text-sm font-medium text-foreground">
          {message || "Memproses pertanyaan..."}
        </span>
        <span className="text-xs font-semibold text-primary">{progress}%</span>
        {onCancel && (
          <Button
            type="button"
            variant="ghost"
            size="icon"
            onClick={onCancel}
            aria-label="Batalkan"
            className="h-9 w-9 text-muted-foreground hover:bg-transparent hover:text-foreground"
          >
            <X className="h-3.5 w-3.5" />
          </Button>
        )}
      </div>
      <Progress value={progress} className="h-2" />
    </div>
  );
}
