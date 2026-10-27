import { Link, useRouter } from "@tanstack/react-router";
import { forwardRef } from "react";
import type { ComponentPropsWithoutRef } from "react";

type AppLinkProps = ComponentPropsWithoutRef<"a"> & {
  activeOptions?: { exact?: boolean };
};

export const AppLink = forwardRef<HTMLAnchorElement, AppLinkProps>(function AppLink(
  { href, activeOptions, ...props },
  ref,
) {
  const router = useRouter({ warn: false });
  if (
    !router ||
    !href?.startsWith("/") ||
    href.startsWith("//") ||
    (props.download !== undefined && props.download !== false)
  )
    return <a {...props} href={href} ref={ref} />;
  return <Link {...props} to={href} activeOptions={activeOptions} ref={ref} />;
});
