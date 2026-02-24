interface SkeletonProps {
  className?: string;
}

export function Skeleton({ className = "h-4 w-full" }: SkeletonProps) {
  return <div className={`rounded-lg shimmer-bg ${className}`} />;
}

interface SkeletonListProps {
  count?: number;
  height?: string;
  gap?: string;
}

export function SkeletonList({ count = 3, height = "h-12", gap = "space-y-2" }: SkeletonListProps) {
  return (
    <div className={gap}>
      {Array.from({ length: count }).map((_, i) => (
        <Skeleton key={i} className={`${height} w-full`} />
      ))}
    </div>
  );
}
