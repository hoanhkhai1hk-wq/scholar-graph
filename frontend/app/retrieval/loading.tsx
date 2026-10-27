import Skeleton, { SkeletonTable } from "@/components/Skeleton";

export default function Loading() {
  return (
    <main className="sg-shell">
      <div className="sg-page-head">
        <Skeleton rows={2} height={16} />
      </div>
      <section className="sg-section">
        <SkeletonTable rows={5} />
      </section>
    </main>
  );
}
