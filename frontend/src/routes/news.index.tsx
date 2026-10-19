import { useSuspenseQuery } from "@tanstack/react-query";
import { createFileRoute } from "@tanstack/react-router";

import { News } from "../features/news/News";
import { newsQuery, newsSearchSchema } from "../shared/api/news";
import { AppError, AppLoading } from "../shared/ui/AppStatus";

export const Route = createFileRoute("/news/")({
  validateSearch: (search) => newsSearchSchema.parse(search),
  loaderDeps: ({ search }) => search,
  loader: ({ context, deps }) => context.queryClient.ensureQueryData(newsQuery(deps)),
  component: NewsPage,
  pendingComponent: () => <AppLoading withinShell label="news" />,
  errorComponent: (props) => <AppError {...props} withinShell section="News" />,
});

function NewsPage() {
  const filters = Route.useSearch();
  const { session } = Route.useRouteContext();
  const { data } = useSuspenseQuery(newsQuery(filters));
  const navigate = Route.useNavigate();
  return (
    <News
      data={data}
      filters={filters}
      isStaff={session.is_staff}
      onFilter={(search, replace) => {
        void navigate({ search, replace });
      }}
    />
  );
}
