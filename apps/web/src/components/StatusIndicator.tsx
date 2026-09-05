import { useEffect, useState } from "react";
import { checkHealth } from "@/lib/api";
import { cn } from "@/lib/utils";

export function StatusIndicator({ compact = false }: { compact?: boolean }) {
  const [online, setOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let mounted = true;
    const run = async () => {
      const ok = await checkHealth();
      if (mounted) setOnline(ok);
    };
    run();
    const id = setInterval(run, 15000);
    return () => {
      mounted = false;
      clearInterval(id);
    };
  }, []);

  const label = online === null ? "Memeriksa..." : online ? "Terhubung" : "Tidak terhubung";
  const color = online === null ? "bg-muted-foreground" : online ? "bg-success" : "bg-destructive";

  if (compact) {
    return (
      <div className="flex items-center gap-2 text-xs">
        <span className={cn("h-2 w-2 rounded-full", color)} />
        <span className="text-muted-foreground">{label}</span>
      </div>
    );
  }

  return (
    <div className="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-muted">
      <span className={cn("h-2.5 w-2.5 rounded-full", color)} />
      <span className="text-xs font-medium text-foreground">{label}</span>
    </div>
  );
}
