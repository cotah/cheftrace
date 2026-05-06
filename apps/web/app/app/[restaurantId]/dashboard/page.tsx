export default function DashboardPage({
  params,
}: {
  params: { restaurantId: string };
}) {
  return (
    <div>
      <h1 className="text-2xl font-semibold">Dashboard</h1>
      <p className="mt-2 text-muted-foreground">
        Restaurant ID: {params.restaurantId}
      </p>
      <p className="mt-4 text-sm text-muted-foreground">
        Full dashboard coming in Sprint 3.
      </p>
    </div>
  );
}
