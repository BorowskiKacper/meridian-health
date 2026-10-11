import type { ReactNode } from "react";
import { cn } from "@/lib/utils";
import type { Severity } from "@/lib/types";

const dot: Record<Severity, string> = {
  critical: "bg-critical",
  watch: "bg-watch",
  clear: "bg-clear",
};

export function SeverityDot({ severity, className }: { severity: Severity; className?: string }) {
  return <span aria-hidden className={cn("inline-block size-2 shrink-0 rounded-full", dot[severity], className)} />;
}

export function PageHeader({
  title,
  children,
  actions,
}: {
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex flex-wrap items-start justify-between gap-x-6 gap-y-4">
      <div className="min-w-0 flex-1 basis-64">
        <h1 className="break-words text-[30px] leading-[1.15] tracking-[-0.01em]">{title}</h1>
        {children && <div className="mt-3 text-[15px] leading-relaxed text-ink-soft">{children}</div>}
      </div>
      {actions && <div className="flex max-w-full flex-wrap items-center gap-2">{actions}</div>}
    </header>
  );
}

export function Section({ title, children, className }: { title: string; children: ReactNode; className?: string }) {
  return (
    <section className={cn("mt-12", className)}>
      <h2 className="eyebrow font-sans">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

export function Page({ children, wide }: { children: ReactNode; wide?: boolean }) {
  return <div className={cn("w-full px-5 py-7 @min-[600px]:px-8 @min-[1200px]:px-10", wide ? "max-w-7xl" : "max-w-5xl")}>{children}</div>;
}

export function StatusText({ status }: { status: "approved" | "rejected" | "pending" }) {
  if (status === "pending") return <span className="text-jade-700">Waiting for you</span>;
  return <span className={status === "approved" ? "text-jade-700" : "text-ink-faint"}>{status === "approved" ? "Approved" : "Rejected"}</span>;
}
