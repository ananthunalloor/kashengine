import { createFileRoute } from "@tanstack/react-router";

import { runQuery } from "../shared/api/ops";
import { opsPageQuery, opsSearchSchema } from "../shared/api/opsWorkspace";
import { OpsPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/ops/$")({
  beforeLoad: ({ context, params }) => {
    const path = params._splat?.replace(/\/$/, "") ?? "";
    const run = path.match(/^runs\/(\d+)$/);
    return run
      ? context.queryClient.ensureQueryData(runQuery(run[1]))
      : context.queryClient.ensureQueryData(opsPageQuery(`${path}/`, opsSearchSchema.parse({})));
  },
  component: OpsRoute,
});

function OpsRoute() {
  const { _splat } = Route.useParams();
  return <OpsPage path={`ops/${_splat ?? ""}`} />;
}
