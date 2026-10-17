import { EmptyState } from "../components/EmptyState";
import { PageHeader } from "../components/PageHeader";

export function PlaceholderPage({ title, description, note }: { title: string; description: string; note: string }) {
  return (
    <>
      <PageHeader title={title} description={description} />
      <EmptyState title="Not built yet">{note}</EmptyState>
    </>
  );
}
