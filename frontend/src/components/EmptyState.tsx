import type { LucideIcon } from "lucide-react";

interface EmptyStateProps {
  icon: LucideIcon;
  title: string;
  hint?: string;
}

export default function EmptyState({ icon: Icon, title, hint }: EmptyStateProps) {
  return (
    <div className="flex flex-col items-center justify-center py-8 px-6">
      <div className="w-12 h-12 rounded-xl bg-surface2/60 flex items-center justify-center mb-3">
        <Icon size={24} strokeWidth={1.5} className="text-subtext/60" />
      </div>
      <p className="text-sm text-text2 text-center font-medium">{title}</p>
      {hint && (
        <p className="text-xs text-subtext text-center mt-1.5 max-w-[220px] leading-relaxed">
          {hint}
        </p>
      )}
    </div>
  );
}
