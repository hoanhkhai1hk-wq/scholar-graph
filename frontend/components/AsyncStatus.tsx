import Skeleton from "./Skeleton";

/** Preserve an honest loading label and the destination's occupied space. */
export default function AsyncStatus({ label, rows = 3 }: { label: string; rows?: number }) {
  return <div className="sg-async-loading" role="status" aria-live="polite" aria-busy="true"><p>{label}</p><Skeleton rows={rows} title={false} /></div>;
}
