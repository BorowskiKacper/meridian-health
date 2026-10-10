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
  eyebrow,
  title,
  children,
  actions,
}: {
  eyebrow: ReactNode;
  title: ReactNode;
  children?: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <header className="flex items-start justify-between gap-8">
      <div className="max-w-2xl">
        <p className="eyebrow">{eyebrow}</p>
        <h1 className="mt-3 text-[34px] leading-[1.1] tracking-[-0.01em]">{title}</h1>
        {children && <div className="mt-3 text-[15px] leading-relaxed text-ink-soft">{children}</div>}
      </div>
      {actions && <div className="flex shrink-0 items-center gap-2 pt-6">{actions}</div>}
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
  return <div className={cn("mx-auto w-full px-12 py-12", wide ? "max-w-7xl" : "max-w-5xl")}>{children}</div>;
}

export function StatusText({ status }: { status: "approved" | "rejected" | "pending" }) {
  if (status === "pending") return <span className="text-jade-700">Waiting for you</span>;
  return <span className={status === "approved" ? "text-jade-700" : "text-ink-faint"}>{status === "approved" ? "Approved" : "Rejected"}</span>;
}
