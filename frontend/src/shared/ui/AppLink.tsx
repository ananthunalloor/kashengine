import { Link, useRouter } from "@tanstack/react-router";
import { forwardRef } from "react";
import type { ComponentPropsWithoutRef } from "react";

export const AppLink = forwardRef<HTMLAnchorElement, ComponentPropsWithoutRef<"a">>(
  function AppLink({ href, ...props }, ref) {
    const router = useRouter({ warn: false });
    if (
      !router ||
      !href?.startsWith("/") ||
      href.startsWith("//") ||
      (props.download !== undefined && props.download !== false)
    )
      return <a {...props} href={href} ref={ref} />;
    return <Link {...props} to={href} ref={ref} />;
  },
);
