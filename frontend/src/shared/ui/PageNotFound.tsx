import { LuArrowLeft, LuHouse } from "react-icons/lu";

import { usePageTitle } from "./usePageTitle";

export function PageNotFound() {
  usePageTitle("Page not found");
  return (
    <section className="public-auth" aria-labelledby="not-found-title">
      <p className="app-eyebrow">404</p>
      <h1 id="not-found-title" tabIndex={-1}>
        Page not found
      </h1>
      <p>
        This page does not exist or may have moved. Check the address or use one of the links below.
      </p>
      <div className="public-actions">
        <a className="public-button" href="/app/landing/">
          <LuHouse aria-hidden="true" />
          Go to home
        </a>
        <a href="/app/dashboard/">
          <LuArrowLeft aria-hidden="true" />
          Open dashboard
        </a>
      </div>
    </section>
  );
}
