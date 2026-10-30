import { createFileRoute } from "@tanstack/react-router";

import {
  auditQuery,
  auditSearchSchema,
  runQuery,
  runSearchSchema,
  runsQuery,
} from "../shared/api/ops";
import { opsPageQuery, opsSearchSchema } from "../shared/api/opsWorkspace";
import { OpsPage } from "../v2/pages/DataDriven";

export const Route = createFileRoute("/v2/_app/ops/$")({
  beforeLoad: ({ context, params, search }) => {
    const path = params._splat?.replace(/\/$/, "") ?? "";
    const run = path.match(/^runs\/(\d+)$/);
    if (run) return context.queryClient.ensureQueryData(runQuery(run[1]));
    if (path === "runs")
      return context.queryClient.ensureQueryData(runsQuery(runSearchSchema.parse(search)));
    if (path === "audit")
      return context.queryClient.ensureQueryData(auditQuery(auditSearchSchema.parse(search)));
    return context.queryClient.ensureQueryData(
      opsPageQuery(`${path}/`, opsSearchSchema.parse(search)),
    );
  },
  component: OpsRoute,
});

function OpsRoute() {
  const { _splat } = Route.useParams();
  return <OpsPage path={`ops/${_splat ?? ""}`} />;
}
